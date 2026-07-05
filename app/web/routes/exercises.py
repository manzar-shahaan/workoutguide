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

VALID_MODALITIES = {"strength", "cardio", "mobility", "plyometrics"}
VALID_CARDIO_TARGETS = {"steady", "hiit", "intervals", "sprints"}


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

        if workout_id is not None:
            # Ensure this workout belongs to the current user
            workout = workouts_repo.get_workout(conn, workout_id, user_id=user_id)
            if workout is None:
                abort(404)

        if request.method == "POST":
            notes = request.form.get("notes", "").strip() or None
            exercise_name = _normalize_exercise_name(request.form.get("exercise_name", ""))
            weight_unit = request.form.get("weight_unit", "").strip() or default_unit
            sets_json_raw = request.form.get("sets_json", "[]")
            modality, cardio_target, modality_error = _parse_modality(request.form)

            if weight_unit not in VALID_WEIGHT_UNITS:
                error = "Please select a valid weight unit."
                return render_template(
                    "exercises/new.html",
                    workout=workout,
                    error=error,
                    today=today_str,
                    max_date=max_date_str,
                    weight_units=WEIGHT_UNITS,
                    weight_unit_selected=weight_unit,
                    sets_json=sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            if modality_error:
                return render_template(
                    "exercises/new.html",
                    workout=workout,
                    error=modality_error,
                    today=today_str,
                    max_date=max_date_str,
                    weight_units=WEIGHT_UNITS,
                    weight_unit_selected=weight_unit,
                    sets_json=sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            try:
                sets = _parse_sets_json(sets_json_raw, weight_unit)
            except ValueError as exc:
                return render_template(
                    "exercises/new.html",
                    workout=workout,
                    error=str(exc),
                    today=today_str,
                    max_date=max_date_str,
                    weight_units=WEIGHT_UNITS,
                    weight_unit_selected=weight_unit,
                    sets_json=sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )
            rollup = _rollup_from_sets(sets)

            if workout is None:
                # No workout_id passed → "new workout + exercise" flow.
                date_str = request.form.get("date", "").strip()

                if not date_str:
                    error = "Date is required when creating a new workout."
                    return render_template(
                        "exercises/new.html",
                        workout=None,
                        error=error,
                        today=today_str,
                        max_date=max_date_str,
                        weight_units=WEIGHT_UNITS,
                        weight_unit_selected=weight_unit,
                        sets_json=sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )

                # Validate date format
                try:
                    selected_date = date.fromisoformat(date_str)
                except ValueError:
                    error = "Invalid date format."
                    return render_template(
                        "exercises/new.html",
                        workout=None,
                        error=error,
                        today=today_str,
                        max_date=max_date_str,
                        weight_units=WEIGHT_UNITS,
                        weight_unit_selected=weight_unit,
                        sets_json=sets_json_raw,
                        modality=modality,
                        cardio_target=cardio_target,
                    )

                # Enforce future date ≤ 7 days
                if selected_date > max_future_date:
                    error = "You can only pick a date up to 7 days in the future."
                    return render_template(
                        "exercises/new.html",
                        workout=None,
                        error=error,
                        today=today_str,
                        max_date=max_date_str,
                        weight_units=WEIGHT_UNITS,
                        weight_unit_selected=weight_unit,
                        sets_json=sets_json_raw,
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
                    if modality == "cardio"
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
                weight_used=rollup["weight_used"],
                weight_unit=weight_unit,
                weight_used_kg=rollup["weight_used_kg"],
                num_of_sets=rollup["num_of_sets"],
                avg_reps=rollup["avg_reps"],
                max_reps=rollup["max_reps"],
                sets=sets,
            )

            # After creating, go back to that workout's detail page
            return redirect(url_for("web.workout_detail", workout_id=workout_id_to_use))

        # GET -- blank form; if arriving from the map/shortlist, main.js
        # fills in exercise_name/sets_json from query params.
        return render_template(
            "exercises/new.html",
            workout=workout,
            error=None,
            today=today_str,
            max_date=max_date_str,
            weight_units=WEIGHT_UNITS,
            weight_unit_selected=default_unit,
            sets_json="[]",
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

        if request.method == "POST":
            date_str = request.form.get("date", "").strip()
            notes = request.form.get("notes", "").strip() or None
            exercise_name = _normalize_exercise_name(request.form.get("exercise_name", ""))
            weight_unit = request.form.get("weight_unit", "").strip() or exercise_unit
            sets_json_raw = request.form.get("sets_json", "[]")
            modality, cardio_target, modality_error = _parse_modality(request.form)

            if weight_unit not in VALID_WEIGHT_UNITS:
                error = "Please select a valid weight unit."
                return render_template(
                    "exercises/edit.html",
                    exercise=exercise,
                    workout=workout,
                    error=error,
                    max_date=max_date_str,
                    exercise_date=workout_date_str,
                    weight_units=WEIGHT_UNITS,
                    weight_unit_selected=weight_unit,
                    sets_json=sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            if modality_error:
                return render_template(
                    "exercises/edit.html",
                    exercise=exercise,
                    workout=workout,
                    error=modality_error,
                    max_date=max_date_str,
                    exercise_date=workout_date_str,
                    weight_units=WEIGHT_UNITS,
                    weight_unit_selected=weight_unit,
                    sets_json=sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            # Validate date
            if not date_str:
                error = "Workout date is required."
                return render_template(
                    "exercises/edit.html",
                    exercise=exercise,
                    workout=workout,
                    error=error,
                    max_date=max_date_str,
                    exercise_date=workout_date_str,
                    weight_units=WEIGHT_UNITS,
                    weight_unit_selected=weight_unit,
                    sets_json=sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            try:
                selected_date = date.fromisoformat(date_str)
            except ValueError:
                error = "Invalid date format."
                return render_template(
                    "exercises/edit.html",
                    exercise=exercise,
                    workout=workout,
                    error=error,
                    max_date=max_date_str,
                    exercise_date=workout_date_str,
                    weight_units=WEIGHT_UNITS,
                    weight_unit_selected=weight_unit,
                    sets_json=sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            if selected_date > max_future_date:
                error = "You can only pick a date up to 7 days in the future."
                return render_template(
                    "exercises/edit.html",
                    exercise=exercise,
                    workout=workout,
                    error=error,
                    max_date=max_date_str,
                    exercise_date=workout_date_str,
                    weight_units=WEIGHT_UNITS,
                    weight_unit_selected=weight_unit,
                    sets_json=sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )

            try:
                sets = _parse_sets_json(sets_json_raw, weight_unit)
            except ValueError as exc:
                return render_template(
                    "exercises/edit.html",
                    exercise=exercise,
                    workout=workout,
                    error=str(exc),
                    max_date=max_date_str,
                    exercise_date=workout_date_str,
                    weight_units=WEIGHT_UNITS,
                    weight_unit_selected=weight_unit,
                    sets_json=sets_json_raw,
                    modality=modality,
                    cardio_target=cardio_target,
                )
            rollup = _rollup_from_sets(sets)

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
                    if modality == "cardio"
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
                weight_used=rollup["weight_used"],
                weight_unit=weight_unit,
                weight_used_kg=rollup["weight_used_kg"],
                num_of_sets=rollup["num_of_sets"],
                avg_reps=rollup["avg_reps"],
                max_reps=rollup["max_reps"],
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
        sets_json_value = json.dumps(
            [{"weight_used": s["weight_used"], "reps": s["reps"]} for s in existing_sets]
        )
        return render_template(
            "exercises/edit.html",
            exercise=exercise,
            workout=workout,
            error=None,
            max_date=max_date_str,
            exercise_date=workout_date_str,
            weight_units=WEIGHT_UNITS,
            weight_unit_selected=exercise_unit,
            region_slugs=region_slugs_value,
            sets_json=sets_json_value,
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
            "exercise_count": row.get("exercise_count", 0),
            "last_weight_used": row.get("last_weight_used"),
            "last_weight_unit": row.get("last_weight_unit"),
            "last_num_of_sets": row.get("last_num_of_sets"),
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
