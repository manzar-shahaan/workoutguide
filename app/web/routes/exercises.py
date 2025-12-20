# app/web/routes/exercises.py
# app/web/routes/exercises.py

import sqlite3
from datetime import date, timedelta  # ⬅️ updated import

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    abort,
    g,
    flash,
)
from ...db.connection import get_conn
from ...db.repositories import workouts as workouts_repo
from ...db.repositories import exercises as exercises_repo
from .. import web_bp
from ..auth_utils import login_required
from ...db.repositories import muscles as muscles_repo


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

        # Fetch all muscles for the dropdown
        muscles = muscles_repo.list_muscles(conn)

        if workout_id is not None:
            # Ensure this workout belongs to the current user
            workout = workouts_repo.get_workout(conn, workout_id, user_id=user_id)
            if workout is None:
                abort(404)

        if request.method == "POST":
            notes = request.form.get("notes", "").strip() or None
            weight_str = request.form.get("weight_used", "").strip()
            sets_str = request.form.get("num_of_sets", "").strip()
            muscle_str = request.form.get("muscle_id", "").strip()

            weight_used = float(weight_str) if weight_str else None
            num_of_sets = int(sets_str) if sets_str else None

            # --- Muscle REQUIRED validation ---
            if not muscle_str:
                error = "Please select a muscle group."
                return render_template(
                    "exercises/new.html",
                    workout=workout,
                    muscles=muscles,
                    error=error,
                    today=today_str,
                    max_date=max_date_str,
                )

            try:
                muscle_id = int(muscle_str)
            except ValueError:
                error = "Invalid muscle selection."
                return render_template(
                    "exercises/new.html",
                    workout=workout,
                    muscles=muscles,
                    error=error,
                    today=today_str,
                    max_date=max_date_str,
                )

            if workout is None:
                # No workout_id passed → "new workout + exercise" flow.
                date_str = request.form.get("date", "").strip()

                if not date_str:
                    error = "Date is required when creating a new workout."
                    return render_template(
                        "exercises/new.html",
                        workout=None,
                        muscles=muscles,
                        error=error,
                        today=today_str,
                        max_date=max_date_str,
                    )

                # Validate date format
                try:
                    selected_date = date.fromisoformat(date_str)
                except ValueError:
                    error = "Invalid date format."
                    return render_template(
                        "exercises/new.html",
                        workout=None,
                        muscles=muscles,
                        error=error,
                        today=today_str,
                        max_date=max_date_str,
                    )

                # Enforce future date ≤ 7 days
                if selected_date > max_future_date:
                    error = "You can only pick a date up to 7 days in the future."
                    return render_template(
                        "exercises/new.html",
                        workout=None,
                        muscles=muscles,
                        error=error,
                        today=today_str,
                        max_date=max_date_str,
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

            exercises_repo.create_exercise(
                conn,
                workout_id=workout_id_to_use,
                notes=notes,
                weight_used=weight_used,
                num_of_sets=num_of_sets,
                muscle_id=muscle_id,
            )

            # After creating, go back to that workout's detail page
            return redirect(url_for("web.workout_detail", workout_id=workout_id_to_use))

        # GET
        return render_template(
            "exercises/new.html",
            workout=workout,
            muscles=muscles,
            error=None,
            today=today_str,
            max_date=max_date_str,
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

        # Load exercise with muscle_id
        exercise = exercises_repo.get_exercise_with_muscle(conn, exercise_id)
        if exercise is None:
            abort(404)

        # Ensure the exercise belongs to a workout owned by this user
        workout = workouts_repo.get_workout(conn, exercise["workout_id"], user_id=user_id)
        if workout is None:
            abort(404)

        # For the dropdown
        muscles = muscles_repo.list_muscles(conn)

        if request.method == "POST":
            date_str = request.form.get("date", "").strip()
            notes = request.form.get("notes", "").strip() or None
            weight_str = request.form.get("weight_used", "").strip()
            sets_str = request.form.get("num_of_sets", "").strip()
            muscle_str = request.form.get("muscle_id", "").strip()

            # Validate date
            if not date_str:
                error = "Workout date is required."
                return render_template(
                    "exercises/edit.html",
                    exercise=exercise,
                    workout=workout,
                    muscles=muscles,
                    error=error,
                    max_date=max_date_str,
                    exercise_date=workout["date"],
                )

            try:
                selected_date = date.fromisoformat(date_str)
            except ValueError:
                error = "Invalid date format."
                return render_template(
                    "exercises/edit.html",
                    exercise=exercise,
                    workout=workout,
                    muscles=muscles,
                    error=error,
                    max_date=max_date_str,
                    exercise_date=workout["date"],
                )

            if selected_date > max_future_date:
                error = "You can only pick a date up to 7 days in the future."
                return render_template(
                    "exercises/edit.html",
                    exercise=exercise,
                    workout=workout,
                    muscles=muscles,
                    error=error,
                    max_date=max_date_str,
                    exercise_date=workout["date"],
                )

            weight_used = float(weight_str) if weight_str else None
            num_of_sets = int(sets_str) if sets_str else None
            muscle_id = int(muscle_str) if muscle_str else None

            # Decide which workout this exercise should belong to after the edit
            current_workout_id = workout["id"]
            current_date_str = workout["date"]

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

            exercises_repo.update_exercise(
                conn,
                exercise_id=exercise_id,
                notes=notes,
                weight_used=weight_used,
                num_of_sets=num_of_sets,
                muscle_id=muscle_id,
                workout_id=target_workout_id,
            )

            # If we moved the exercise to a different workout, clean up an empty original workout
            if target_workout_id != current_workout_id:
                remaining = exercises_repo.count_exercises_for_workout(conn, current_workout_id)
                if remaining == 0:
                    workouts_repo.delete_workout(conn, current_workout_id, user_id)

            flash("Exercise updated.", "success")
            return redirect(url_for("web.workout_detail", workout_id=target_workout_id))

        # GET → show form with current values
        return render_template(
            "exercises/edit.html",
            exercise=exercise,
            workout=workout,
            muscles=muscles,
            error=None,
            max_date=max_date_str,
            exercise_date=workout["date"],
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
        exercise = exercises_repo.get_exercise_with_muscle(conn, exercise_id)
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
