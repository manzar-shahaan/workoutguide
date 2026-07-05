# app/web/routes/exercises.py

import json
from datetime import date, datetime, timedelta  # ⬅️ updated import

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    abort,
    g,
    flash,
    jsonify,
)
from ...db.connection import get_conn
from ...db.repositories import workouts as workouts_repo
from ...db.repositories import exercises as exercises_repo
from ...db.repositories import exercise_catalog as exercise_catalog_repo
from .. import web_bp
from ..auth_utils import login_required
from ...db.repositories import suggested_exercises as suggested_exercises_repo
from utils.date_utils import format_date
from utils.body_regions import REGION_SLUGS

WEIGHT_UNITS = [
    {"id": "lb", "name": "lb"},
    {"id": "kg", "name": "kg"},
]
VALID_WEIGHT_UNITS = {"lb", "kg"}
LB_TO_KG = 0.45359237

DISTANCE_UNITS = [
    {"id": "mi", "name": "mi"},
    {"id": "km", "name": "km"},
]
VALID_DISTANCE_UNITS = {"mi", "km"}

VALID_MODALITIES = {"strength", "cardio", "mobility", "plyometrics"}
VALID_CARDIO_TARGETS = {"steady", "hiit", "intervals", "sprints"}


def _default_distance_unit(weight_unit_pref: str) -> str:
    """Mirrors the US/metric split already implied by the weight unit pref."""
    return "mi" if weight_unit_pref == "lb" else "km"


def _parse_modality(form) -> tuple[str, str | None, str | None]:
    """
    Returns (modality, cardio_target, error). Cardio requires picking one
    of the 4 targets; every other modality is tagged via the region map
    instead, so cardio_target is forced to None for those regardless of
    what's in the submitted form (stale hidden-field state from switching
    the picker shouldn't leak through).
    """
    modality = form.get("modality", "").strip() or "strength"
    if modality not in VALID_MODALITIES:
        return modality, None, "Please select a valid exercise type."

    if modality != "cardio":
        return modality, None, None

    cardio_target = form.get("cardio_target", "").strip()
    if cardio_target not in VALID_CARDIO_TARGETS:
        return modality, None, "Please select a cardio type."
    return modality, cardio_target, None


def _normalize_weight_to_kg(weight_used: float | None, weight_unit: str | None) -> float | None:
    if weight_used is None:
        return None
    if weight_unit == "kg":
        return float(weight_used)
    if weight_unit == "lb":
        return float(weight_used) * LB_TO_KG
    return None


def _parse_sets_json(raw_json: str, weight_unit: str) -> list[dict]:
    """
    Parses the set-list.js hidden field into normalized set dicts, dropping
    empty rows (no weight and no reps -- an unused row left over from
    "Add set"). Raises ValueError with a user-facing message on bad input.
    """
    try:
        raw_sets = json.loads(raw_json) if raw_json else []
    except (ValueError, TypeError):
        raise ValueError("Could not read the sets you entered. Please try again.")

    if not isinstance(raw_sets, list):
        raise ValueError("Could not read the sets you entered. Please try again.")

    sets = []
    for raw_set in raw_sets:
        if not isinstance(raw_set, dict):
            continue
        weight_used = raw_set.get("weight_used")
        reps = raw_set.get("reps")
        if weight_used is None and reps is None:
            continue  # unused row

        try:
            weight_used = float(weight_used) if weight_used is not None else None
            reps = int(reps) if reps is not None else None
        except (TypeError, ValueError):
            raise ValueError("Please enter valid numbers for each set's weight and reps.")

        if reps is not None and reps <= 0:
            raise ValueError("Reps must be greater than 0.")

        sets.append(
            {
                "weight_used": weight_used,
                "weight_unit": weight_unit if weight_used is not None else None,
                "weight_used_kg": _normalize_weight_to_kg(weight_used, weight_unit),
                "reps": reps,
            }
        )

    if not sets:
        raise ValueError("Please log at least one set.")
    return sets


def _rollup_from_sets(sets: list[dict]) -> dict:
    """
    Derives the exercise-level summary columns (top-set weight, count,
    avg/max reps) from real set rows, for quick-list display. Volume and
    progression stats read the set rows directly, not these.
    """
    reps_list = [s["reps"] for s in sets if s["reps"] is not None]
    weighted = [s for s in sets if s["weight_used"] is not None]
    top_set = max(weighted, key=lambda s: s["weight_used"]) if weighted else None

    return {
        "num_of_sets": len(sets),
        "avg_reps": (sum(reps_list) / len(reps_list)) if reps_list else None,
        "max_reps": max(reps_list) if reps_list else None,
        "weight_used": top_set["weight_used"] if top_set else None,
        "weight_used_kg": top_set["weight_used_kg"] if top_set else None,
    }


def _parse_cardio_sets_json(raw_json: str, distance_unit: str) -> list[dict]:
    """
    Parses cardio-set-list.js's hidden field into normalized interval
    dicts. Steady-state cardio is one row; HIIT/intervals/sprints can have
    several, one per interval -- same "Add row" pattern as strength sets,
    just duration/distance instead of weight/reps.
    """
    try:
        raw_sets = json.loads(raw_json) if raw_json else []
    except (ValueError, TypeError):
        raise ValueError("Could not read the intervals you entered. Please try again.")

    if not isinstance(raw_sets, list):
        raise ValueError("Could not read the intervals you entered. Please try again.")

    sets = []
    for raw_set in raw_sets:
        if not isinstance(raw_set, dict):
            continue
        duration_seconds = raw_set.get("duration_seconds")
        distance = raw_set.get("distance")
        if duration_seconds is None and distance is None:
            continue  # unused row

        try:
            duration_seconds = int(duration_seconds) if duration_seconds is not None else None
            distance = float(distance) if distance is not None else None
        except (TypeError, ValueError):
            raise ValueError("Please enter valid values for each interval's time and distance.")

        if duration_seconds is not None and duration_seconds <= 0:
            raise ValueError("Duration must be greater than 0.")
        if distance is not None and distance <= 0:
            raise ValueError("Distance must be greater than 0.")

        sets.append(
            {
                "duration_seconds": duration_seconds,
                "distance": distance,
                "distance_unit": distance_unit if distance is not None else None,
            }
        )

    if not sets:
        raise ValueError("Please log at least one interval.")
    return sets


def _rollup_from_cardio_sets(sets: list[dict]) -> dict:
    """
    Derives the exercise-level summary columns (total time, total
    distance) from real interval rows, mirroring _rollup_from_sets.
    """
    durations = [s["duration_seconds"] for s in sets if s["duration_seconds"] is not None]
    distances = [s["distance"] for s in sets if s["distance"] is not None]
    distance_unit = next((s["distance_unit"] for s in sets if s["distance_unit"]), None)

    return {
        "num_of_sets": len(sets),
        "total_duration_seconds": sum(durations) if durations else None,
        "total_distance": sum(distances) if distances else None,
        "distance_unit": distance_unit,
    }


def _normalize_exercise_name(value: str | None) -> str | None:
    if not value:
        return None
    name = value.strip().lower()
    return name or None


def _date_to_str(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _format_last_logged(raw_date) -> str | None:
    if not raw_date:
        return None
    date_obj = raw_date if isinstance(raw_date, date) else datetime.strptime(raw_date, "%Y-%m-%d").date()
    return format_date(date_obj)


@web_bp.route("/exercises/new", methods=["GET", "POST"])
@login_required
def new_exercise():
    conn = get_conn()
    try:
        user_id = g.user["id"]
        workout_id = request.args.get("workout_id", type=int)
        workout = None

        # For date defaults + validation
        today = date.today()
        today_str = today.isoformat()
        max_future_date = today + timedelta(days=7)
        max_date_str = max_future_date.isoformat()

        default_unit = g.user.get("weight_unit") or "lb"
        default_distance_unit = _default_distance_unit(default_unit)

        if workout_id is not None:
            # Ensure this workout belongs to the current user
            workout = workouts_repo.get_workout(conn, workout_id, user_id=user_id)
            if workout is None:
                abort(404)

        def render_form(*, error, weight_unit, distance_unit, sets_json, cardio_sets_json, modality, cardio_target):
            return render_template(
                "exercises/new.html",
                workout=workout,
                error=error,
                today=today_str,
                max_date=max_date_str,
                weight_units=WEIGHT_UNITS,
                weight_unit_selected=weight_unit,
                distance_units=DISTANCE_UNITS,
                distance_unit_selected=distance_unit,
                sets_json=sets_json,
                cardio_sets_json=cardio_sets_json,
                modality=modality,
                cardio_target=cardio_target,
            )

        if request.method == "POST":
            notes = request.form.get("notes", "").strip() or None
            exercise_name = _normalize_exercise_name(request.form.get("exercise_name", ""))
            modality, cardio_target, modality_error = _parse_modality(request.form)

            weight_unit = request.form.get("weight_unit", "").strip() or default_unit
            distance_unit = request.form.get("distance_unit", "").strip() or default_distance_unit
            sets_json_raw = request.form.get("sets_json", "[]")
            cardio_sets_json_raw = request.form.get("cardio_sets_json", "[]")

            if modality_error:
                return render_form(
                    error=modality_error,
                    weight_unit=weight_unit,
                    distance_unit=distance_unit,
                    sets_json=sets_json_raw,
                    cardio_sets_json=cardio_sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            is_cardio = modality == "cardio"

            if is_cardio:
                if distance_unit not in VALID_DISTANCE_UNITS:
                    return render_form(
                        error="Please select a valid distance unit.",
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )
                try:
                    sets = _parse_cardio_sets_json(cardio_sets_json_raw, distance_unit)
                except ValueError as exc:
                    return render_form(
                        error=str(exc),
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )
                rollup = _rollup_from_cardio_sets(sets)
                weight_unit_to_store = None
            else:
                if weight_unit not in VALID_WEIGHT_UNITS:
                    return render_form(
                        error="Please select a valid weight unit.",
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )
                try:
                    sets = _parse_sets_json(sets_json_raw, weight_unit)
                except ValueError as exc:
                    return render_form(
                        error=str(exc),
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )
                rollup = _rollup_from_sets(sets)
                weight_unit_to_store = weight_unit

            if workout is None:
                # No workout_id passed → "new workout + exercise" flow.
                date_str = request.form.get("date", "").strip()

                if not date_str:
                    return render_form(
                        error="Date is required when creating a new workout.",
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )

                # Validate date format
                try:
                    selected_date = date.fromisoformat(date_str)
                except ValueError:
                    return render_form(
                        error="Invalid date format.",
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )

                # Enforce future date ≤ 7 days
                if selected_date > max_future_date:
                    return render_form(
                        error="You can only pick a date up to 7 days in the future.",
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )

                # Past dates are allowed (for backfilling), so no lower bound.
                # Link to existing or create new workout for that date.
                existing = workouts_repo.find_by_user_and_date(conn, user_id, date_str)
                if existing is not None:
                    workout_id_to_use = existing["id"]
                else:
                    workout_id_to_use = workouts_repo.create_workout(
                        conn,
                        user_id=user_id,
                        date=date_str,
                        notes=None,
                    )
            else:
                # Adding exercise into an existing workout
                workout_id_to_use = workout["id"]

            exercise_catalog_id = None
            if exercise_name:
                exercise_catalog_id = exercise_catalog_repo.get_or_create(
                    conn,
                    user_id=user_id,
                    name=exercise_name,
                    modality=modality,
                    cardio_target=cardio_target,
                )
                # Re-logging with a different modality than it was created
                # with (e.g. "running" first tagged steady, later intervals)
                # should update the catalog entry, not just the new log.
                exercise_catalog_repo.set_modality(conn, exercise_catalog_id, modality, cardio_target)

                # Cardio is classified by cardio_target, not body regions --
                # clear any stale region tags rather than let them linger.
                # Always write, even when empty: tag_regions is a full
                # replace, so submitting no regions means "untag this."
                region_slugs = (
                    []
                    if is_cardio
                    else [
                        slug.strip()
                        for slug in request.form.get("region_slugs", "").split(",")
                        if slug.strip() in REGION_SLUGS
                    ]
                )
                exercise_catalog_repo.tag_regions(conn, exercise_catalog_id, region_slugs)

            exercises_repo.create_exercise(
                conn,
                workout_id=workout_id_to_use,
                notes=notes,
                exercise_catalog_id=exercise_catalog_id,
                exercise_name=exercise_name,
                weight_used=rollup.get("weight_used"),
                weight_unit=weight_unit_to_store,
                weight_used_kg=rollup.get("weight_used_kg"),
                num_of_sets=rollup["num_of_sets"],
                avg_reps=rollup.get("avg_reps"),
                max_reps=rollup.get("max_reps"),
                total_duration_seconds=rollup.get("total_duration_seconds"),
                total_distance=rollup.get("total_distance"),
                distance_unit=rollup.get("distance_unit"),
                sets=sets,
            )

            # After creating, go back to that workout's detail page
            return redirect(url_for("web.workout_detail", workout_id=workout_id_to_use))

        # GET -- blank form; if arriving from the map/shortlist, main.js
        # fills in exercise_name/sets_json from query params.
        return render_form(
            error=None,
            weight_unit=default_unit,
            distance_unit=default_distance_unit,
            sets_json="[]",
            cardio_sets_json="[]",
            modality="strength",
            cardio_target=None,
        )
    finally:
        conn.close()



@web_bp.route("/exercises/<int:exercise_id>/edit", methods=["GET", "POST"])
@login_required
def edit_exercise(exercise_id):
    conn = get_conn()
    try:
        user_id = g.user["id"]

        # For date validation (allow backfilling, but only up to 7 days in future)
        today = date.today()
        max_future_date = today + timedelta(days=7)
        max_date_str = max_future_date.isoformat()

        exercise = exercises_repo.get_exercise_with_workout(conn, exercise_id)
        if exercise is None:
            abort(404)

        # Ensure the exercise belongs to a workout owned by this user
        workout = workouts_repo.get_workout(conn, exercise["workout_id"], user_id=user_id)
        if workout is None:
            abort(404)
        workout_date_str = _date_to_str(workout["date"])

        existing_catalog_id = exercise["exercise_catalog_id"] if "exercise_catalog_id" in exercise.keys() else None
        existing_template = (
            exercise_catalog_repo.get_template(conn, user_id, existing_catalog_id)
            if existing_catalog_id
            else None
        )
        current_modality = existing_template["modality"] if existing_template else "strength"
        current_cardio_target = existing_template["cardio_target"] if existing_template else None

        default_unit = g.user.get("weight_unit") or "lb"
        exercise_unit = (
            exercise["weight_unit"]
            if "weight_unit" in exercise.keys() and exercise["weight_unit"]
            else default_unit
        )
        default_distance_unit = _default_distance_unit(default_unit)
        exercise_distance_unit = (
            exercise["distance_unit"]
            if "distance_unit" in exercise.keys() and exercise["distance_unit"]
            else default_distance_unit
        )

        def render_form(*, error, weight_unit, distance_unit, sets_json, cardio_sets_json, modality, cardio_target, region_slugs=None):
            return render_template(
                "exercises/edit.html",
                exercise=exercise,
                workout=workout,
                error=error,
                max_date=max_date_str,
                exercise_date=workout_date_str,
                weight_units=WEIGHT_UNITS,
                weight_unit_selected=weight_unit,
                distance_units=DISTANCE_UNITS,
                distance_unit_selected=distance_unit,
                region_slugs=region_slugs,
                sets_json=sets_json,
                cardio_sets_json=cardio_sets_json,
                modality=modality,
                cardio_target=cardio_target,
            )

        if request.method == "POST":
            date_str = request.form.get("date", "").strip()
            notes = request.form.get("notes", "").strip() or None
            exercise_name = _normalize_exercise_name(request.form.get("exercise_name", ""))
            modality, cardio_target, modality_error = _parse_modality(request.form)

            weight_unit = request.form.get("weight_unit", "").strip() or exercise_unit
            distance_unit = request.form.get("distance_unit", "").strip() or exercise_distance_unit
            sets_json_raw = request.form.get("sets_json", "[]")
            cardio_sets_json_raw = request.form.get("cardio_sets_json", "[]")

            if modality_error:
                return render_form(
                    error=modality_error,
                    weight_unit=weight_unit,
                    distance_unit=distance_unit,
                    sets_json=sets_json_raw,
                    cardio_sets_json=cardio_sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            is_cardio = modality == "cardio"

            if is_cardio:
                if distance_unit not in VALID_DISTANCE_UNITS:
                    return render_form(
                        error="Please select a valid distance unit.",
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )
                try:
                    sets = _parse_cardio_sets_json(cardio_sets_json_raw, distance_unit)
                except ValueError as exc:
                    return render_form(
                        error=str(exc),
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )
                rollup = _rollup_from_cardio_sets(sets)
                weight_unit_to_store = None
            else:
                if weight_unit not in VALID_WEIGHT_UNITS:
                    return render_form(
                        error="Please select a valid weight unit.",
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )
                try:
                    sets = _parse_sets_json(sets_json_raw, weight_unit)
                except ValueError as exc:
                    return render_form(
                        error=str(exc),
                        weight_unit=weight_unit,
                        distance_unit=distance_unit,
                        sets_json=sets_json_raw,
                        cardio_sets_json=cardio_sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )
                rollup = _rollup_from_sets(sets)
                weight_unit_to_store = weight_unit

            # Validate date
            if not date_str:
                return render_form(
                    error="Workout date is required.",
                    weight_unit=weight_unit,
                    distance_unit=distance_unit,
                    sets_json=sets_json_raw,
                    cardio_sets_json=cardio_sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            try:
                selected_date = date.fromisoformat(date_str)
            except ValueError:
                return render_form(
                    error="Invalid date format.",
                    weight_unit=weight_unit,
                    distance_unit=distance_unit,
                    sets_json=sets_json_raw,
                    cardio_sets_json=cardio_sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            if selected_date > max_future_date:
                return render_form(
                    error="You can only pick a date up to 7 days in the future.",
                    weight_unit=weight_unit,
                    distance_unit=distance_unit,
                    sets_json=sets_json_raw,
                    cardio_sets_json=cardio_sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            # Decide which workout this exercise should belong to after the edit
            current_workout_id = workout["id"]
            current_date_str = workout_date_str

            if date_str == current_date_str:
                target_workout_id = current_workout_id
            else:
                existing = workouts_repo.find_by_user_and_date(conn, user_id, date_str)
                if existing is not None:
                    target_workout_id = existing["id"]
                else:
                    target_workout_id = workouts_repo.create_workout(
                        conn,
                        user_id=user_id,
                        date=date_str,
                        notes=None,
                    )

            exercise_catalog_id = None
            if exercise_name:
                exercise_catalog_id = exercise_catalog_repo.get_or_create(
                    conn,
                    user_id=user_id,
                    name=exercise_name,
                    modality=modality,
                    cardio_target=cardio_target,
                )
                exercise_catalog_repo.set_modality(conn, exercise_catalog_id, modality, cardio_target)

                # Cardio is classified by cardio_target, not body regions --
                # clear any stale region tags rather than let them linger.
                # Always write, even when empty: tag_regions is a full
                # replace, so submitting no regions means "untag this."
                region_slugs = (
                    []
                    if is_cardio
                    else [
                        slug.strip()
                        for slug in request.form.get("region_slugs", "").split(",")
                        if slug.strip() in REGION_SLUGS
                    ]
                )
                exercise_catalog_repo.tag_regions(conn, exercise_catalog_id, region_slugs)

            exercises_repo.update_exercise(
                conn,
                exercise_id=exercise_id,
                notes=notes,
                exercise_catalog_id=exercise_catalog_id,
                exercise_name=exercise_name,
                weight_used=rollup.get("weight_used"),
                weight_unit=weight_unit_to_store,
                weight_used_kg=rollup.get("weight_used_kg"),
                num_of_sets=rollup["num_of_sets"],
                avg_reps=rollup.get("avg_reps"),
                max_reps=rollup.get("max_reps"),
                total_duration_seconds=rollup.get("total_duration_seconds"),
                total_distance=rollup.get("total_distance"),
                distance_unit=rollup.get("distance_unit"),
                workout_id=target_workout_id,
                sets=sets,
            )

            # If we moved the exercise to a different workout, clean up an empty original workout
            if target_workout_id != current_workout_id:
                remaining = exercises_repo.count_exercises_for_workout(conn, current_workout_id)
                if remaining == 0:
                    workouts_repo.delete_workout(conn, current_workout_id, user_id)

            flash("Exercise updated.", "success")
            return redirect(url_for("web.workout_detail", workout_id=target_workout_id))

        # GET → show form with current values
        region_slugs_value = (
            ",".join(exercise_catalog_repo.get_regions(conn, existing_catalog_id))
            if existing_catalog_id
            else ""
        )
        existing_sets = exercises_repo.get_sets_for_exercise(conn, exercise_id)
        if current_modality == "cardio":
            sets_json_value = "[]"
            cardio_sets_json_value = json.dumps(
                [{"duration_seconds": s["duration_seconds"], "distance": s["distance"]} for s in existing_sets]
            )
            distance_unit_value = next(
                (s["distance_unit"] for s in existing_sets if s["distance_unit"]),
                default_distance_unit,
            )
        else:
            sets_json_value = json.dumps(
                [{"weight_used": s["weight_used"], "reps": s["reps"]} for s in existing_sets]
            )
            cardio_sets_json_value = "[]"
            distance_unit_value = default_distance_unit

        return render_form(
            error=None,
            weight_unit=exercise_unit,
            distance_unit=distance_unit_value,
            region_slugs=region_slugs_value,
            sets_json=sets_json_value,
            cardio_sets_json=cardio_sets_json_value,
            modality=current_modality,
            cardio_target=current_cardio_target,
        )
    finally:
        conn.close()



@web_bp.route("/exercises/<int:exercise_id>/delete", methods=["POST"])
@login_required
def delete_exercise(exercise_id):
    conn = get_conn()
    try:
        user_id = g.user["id"]

        # Get the exercise and its workout
        exercise = exercises_repo.get_exercise_with_workout(conn, exercise_id)
        if exercise is None:
            abort(404)

        workout_id = exercise["workout_id"]

        # Make sure this workout belongs to the current user
        workout = workouts_repo.get_workout(conn, workout_id, user_id=user_id)
        if workout is None:
            abort(404)

        # Delete the exercise
        exercises_repo.delete_exercise(conn, exercise_id)

        # See if any exercises remain in this workout
        remaining = exercises_repo.count_exercises_for_workout(conn, workout_id)

        if remaining == 0:
            # No more exercises → delete the now-empty workout
            workouts_repo.delete_workout(conn, workout_id, user_id)
            flash("Exercise deleted and empty workout removed.", "success")
            return redirect(url_for("web.workouts_index"))

        # Still has exercises → keep workout, go back to its page
        flash("Exercise deleted.", "success")
        return redirect(url_for("web.workout_detail", workout_id=workout_id))
    finally:
        conn.close()


@web_bp.route("/api/exercises/suggestions")
@login_required
def exercise_suggestions():
    user_id = g.user["id"]
    query = request.args.get("q", "").strip()

    conn = get_conn()
    try:
        total = exercise_catalog_repo.count_for_user(conn, user_id)
        if query:
            items = exercise_catalog_repo.search_all_with_counts(conn, user_id, query)
        else:
            items = exercise_catalog_repo.list_all_with_counts_and_last(conn, user_id)
    finally:
        conn.close()

    formatted = [
        {
            "id": row["id"],
            "name": row["name"],
            "modality": row.get("modality") or "strength",
            "cardio_target": row.get("cardio_target"),
            "exercise_count": row.get("exercise_count", 0),
            "last_weight_used": row.get("last_weight_used"),
            "last_weight_unit": row.get("last_weight_unit"),
            "last_num_of_sets": row.get("last_num_of_sets"),
            "last_total_duration_seconds": row.get("last_total_duration_seconds"),
            "last_total_distance": row.get("last_total_distance"),
            "last_distance_unit": row.get("last_distance_unit"),
            "last_logged": _format_last_logged(row.get("last_workout_date")),
            "last_sets": row.get("last_sets_json") or [],
        }
        for row in items
    ]
    return jsonify({"count": total, "items": formatted})


@web_bp.route("/api/exercises/region-shortlist")
@login_required
def region_shortlist():
    user_id = g.user["id"]
    raw_regions = (request.args.get("regions") or "").strip()
    slugs = [slug for slug in raw_regions.split(",") if slug in REGION_SLUGS]
    if not slugs:
        return jsonify({"regions": [], "your_exercises": [], "suggestions": []})

    conn = get_conn()
    try:
        your_rows = exercise_catalog_repo.list_for_regions(conn, user_id, slugs)
        suggestion_rows = suggested_exercises_repo.list_for_regions(conn, user_id, slugs)
    finally:
        conn.close()

    your_exercises = [
        {
            "id": row["id"],
            "name": row["name"],
            "modality": row.get("modality") or "strength",
            "cardio_target": row.get("cardio_target"),
            "image_url": url_for("web.static", filename=row["image_path"]) if row.get("image_path") else None,
            "last_weight_used": row.get("last_weight_used"),
            "last_weight_unit": row.get("last_weight_unit"),
            "last_num_of_sets": row.get("last_num_of_sets"),
            "last_logged": _format_last_logged(row.get("last_workout_date")),
            "last_sets": row.get("last_sets_json") or [],
        }
        for row in your_rows
    ]

    suggestions = [
        {
            "name": row["name"],
            "image_url": url_for("web.static", filename=row["image_path"]) if row.get("image_path") else None,
            "license_author": row.get("license_author"),
            "license_name": row.get("license_name"),
            "region_slugs": slugs,
        }
        for row in suggestion_rows
    ]

    return jsonify({"regions": slugs, "your_exercises": your_exercises, "suggestions": suggestions})


@web_bp.route("/api/exercises/cardio-list")
@login_required
def cardio_list():
    """
    Cardio catalog entries for the home page's cardio quick-add list --
    the muscle map has nothing to tap for cardio, so this is that mode's
    equivalent "what have you logged before" surface.
    """
    user_id = g.user["id"]
    conn = get_conn()
    try:
        rows = exercise_catalog_repo.list_cardio_with_last(conn, user_id)
    finally:
        conn.close()

    items = [
        {
            "id": row["id"],
            "name": row["name"],
            "cardio_target": row.get("cardio_target"),
            "last_total_duration_seconds": row.get("last_total_duration_seconds"),
            "last_total_distance": row.get("last_total_distance"),
            "last_distance_unit": row.get("last_distance_unit"),
            "last_logged": _format_last_logged(row.get("last_workout_date")),
            "last_sets": row.get("last_sets_json") or [],
        }
        for row in rows
    ]
    return jsonify({"items": items})
