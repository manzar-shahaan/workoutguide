# app/web/routes/auth.py

import json
import re
from datetime import datetime, timezone

from flask import (
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    g,
    Response,
)
from flask_login import login_user, logout_user
from argon2 import PasswordHasher, exceptions as argon2_exceptions
import pyotp

from ...db.connection import get_conn
from ...db.repositories import users as users_repo
from ...db.repositories import muscles as muscles_repo
from ...db.repositories import backup_codes as backup_codes_repo
from ...db.repositories import access_codes as access_codes_repo
from ...db.repositories import workouts as workouts_repo
from .. import web_bp
from ..auth_utils import login_required, make_user

EMAIL_REGEX = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_NAME_LEN = 80
MAX_EMAIL_LEN = 255
MIN_PASSWORD_LEN = 8
MAX_PASSWORD_LEN = 128
MAX_ACCESS_CODE_LEN = 64

# Argon2 password hasher
ph = PasswordHasher()


def row_value(row, key, default=None):
    """
    Safe helper for DB rows:
    - returns row[key] if key exists and value is not None
    - otherwise returns default
    """
    keys = row.keys()
    if key in keys and row[key] is not None:
        return row[key]
    return default



@web_bp.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        access_code = (request.form.get("access_code") or "").strip().replace(" ", "").upper()

        error = None

        if not name:
            error = "Name is required."
        elif len(name) > MAX_NAME_LEN:
            error = f"Name must be at most {MAX_NAME_LEN} characters."
        elif not email:
            error = "Email is required."
        elif len(email) > MAX_EMAIL_LEN:
            error = f"Email must be at most {MAX_EMAIL_LEN} characters."
        elif not EMAIL_REGEX.match(email):
            error = "Please enter a valid email address."
        elif not password:
            error = "Password is required."
        elif len(password) < MIN_PASSWORD_LEN:
            error = f"Password must be at least {MIN_PASSWORD_LEN} characters."
        elif len(password) > MAX_PASSWORD_LEN:
            error = f"Password must be at most {MAX_PASSWORD_LEN} characters."
        elif password != confirm_password:
            error = "Passwords do not match."
        elif not access_code:
            error = "Access code is required."
        elif len(access_code) > MAX_ACCESS_CODE_LEN:
            error = "Access code is invalid."

        conn = get_conn()
        try:
            existing = users_repo.get_user_by_email(conn, email) if email else None
            code_row = access_codes_repo.get_by_code(conn, access_code) if access_code else None
        finally:
            conn.close()

        if existing is not None:
            error = "An account with that email already exists."
        elif error is None and code_row is None:
            error = "Invalid access code."
        elif error is None and code_row and code_row["used_by_user_id"] is not None:
            error = "Access code has already been used."

        if error:
            flash(error, "error")
        else:
            # Hash password with Argon2
            password_hash = ph.hash(password)

            conn = get_conn()
            try:
                user_id = users_repo.create_user(conn, name, email, password_hash)
                code_used = access_codes_repo.mark_used(conn, access_code, user_id)
                if not code_used:
                    users_repo.delete_user(conn, user_id)
                    error = "Access code has already been used."
                else:
                    muscles_repo.ensure_default_muscles(conn, user_id)
                    user_row = users_repo.get_user(conn, user_id)
            finally:
                conn.close()

            if error:
                flash(error, "error")
            else:
                # Log in via Flask-Login
                user_obj = make_user(user_row)
                login_user(user_obj)

                flash("Account created and logged in.", "success")
                return redirect(url_for("web.workouts_index"))

    return render_template("auth/signup.html")


@web_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        error = None

        conn = get_conn()
        try:
            user = users_repo.get_user_by_email(conn, email)
        finally:
            conn.close()

        if user is None:
            error = "Incorrect email or password."
        else:
            try:
                ph.verify(user["password_hash"], password)
            except argon2_exceptions.VerifyMismatchError:
                error = "Incorrect email or password."
            except argon2_exceptions.VerificationError:
                error = "Incorrect email or password."

        if error:
            flash(error, "error")
        else:
            # Check if TOTP 2FA is enabled
            totp_enabled = bool(row_value(user, "totp_enabled", 0))
            has_secret = bool(row_value(user, "totp_secret", None))


            if totp_enabled and has_secret:
                # Step 1 passed → go to 2FA step
                session["pending_2fa_user_id"] = user["id"]
                flash("Enter your 2FA or backup code to complete login.", "info")
                return redirect(url_for("web.login_2fa"))

            # No 2FA → log in directly
            user_obj = make_user(user)
            login_user(user_obj)
            flash("Logged in successfully.", "success")
            return redirect(url_for("web.workouts_index"))

    return render_template("auth/login.html")



@web_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    # Flask-Login logout + clear any extra session data
    logout_user()
    session.clear()
    flash("Successfully logged out.", "success")
    return redirect(url_for("web.login"))


@web_bp.route("/account", methods=["GET", "POST"])
@login_required
def account_settings():
    user_id = g.user["id"]

    # Always load the latest data from DB
    conn = get_conn()
    try:
        db_user = users_repo.get_user(conn, user_id)
    finally:
        conn.close()

    # Default form values
    form_name = db_user["name"]
    form_email = db_user["email"]
    form_recovery_email = (db_user["recovery_email"] or "")

    # Edit mode if ?edit=1 OR we’re handling a POST (after an attempted save)
    edit_mode = request.args.get("edit") == "1" or request.method == "POST"

    if request.method == "POST":
        form_name = (request.form.get("name") or "").strip()
        form_email = (request.form.get("email") or "").strip().lower()
        form_recovery_email = (request.form.get("recovery_email") or "").strip()
        password_confirm = request.form.get("password_confirm", "")

        error = None

        # Basic name/email validation
        if not form_name:
            error = "Name is required."
        elif len(form_name) > MAX_NAME_LEN:
            error = f"Name must be at most {MAX_NAME_LEN} characters."
        elif not form_email:
            error = "Email is required."
        elif len(form_email) > MAX_EMAIL_LEN:
            error = f"Email must be at most {MAX_EMAIL_LEN} characters."
        elif not EMAIL_REGEX.match(form_email):
            error = "Please enter a valid email address."

        # Recovery email validation (if provided)
        if error is None and form_recovery_email:
            if len(form_recovery_email) > MAX_EMAIL_LEN:
                error = f"Recovery email must be at most {MAX_EMAIL_LEN} characters."
            elif not EMAIL_REGEX.match(form_recovery_email):
                error = "Please enter a valid recovery email address."
            elif form_recovery_email.lower() == form_email:
                error = "Recovery email cannot be the same as your primary email."

        recovery_value = form_recovery_email or None

        # Did they change primary or recovery email?
        email_changed = (form_email != db_user["email"])
        old_recovery = db_user["recovery_email"] or ""
        recovery_changed = (form_recovery_email or "") != old_recovery

        # If email/recovery changed, require password confirmation
        if error is None and (email_changed or recovery_changed):
            if not password_confirm:
                error = "Please enter your password to confirm email changes."
            else:
                conn = get_conn()
                try:
                    fresh = users_repo.get_user(conn, user_id)
                finally:
                    conn.close()

                try:
                    ph.verify(fresh["password_hash"], password_confirm)
                except argon2_exceptions.VerifyMismatchError:
                    error = "Incorrect password."
                except argon2_exceptions.VerificationError:
                    error = "Incorrect password."

        # If primary email changed, ensure uniqueness
        if error is None and email_changed:
            conn = get_conn()
            try:
                existing = users_repo.get_user_by_email(conn, form_email)
            finally:
                conn.close()

            if existing is not None and existing["id"] != user_id:
                error = "Another account already uses that email."

        if error:
            flash(error, "error")
            # fall through to re-render in edit mode with current form_* values
        else:
            conn = get_conn()
            try:
                users_repo.update_profile(
                    conn,
                    user_id=user_id,
                    name=form_name,
                    email=form_email,
                    recovery_email=recovery_value,
                )
            finally:
                conn.close()

            flash("Account details updated.", "success")
            return redirect(url_for("web.account_settings"))

    return render_template(
        "account/account.html",
        user=db_user,
        edit_mode=edit_mode,
        form_name=form_name,
        form_email=form_email,
        form_recovery_email=form_recovery_email,
    )


@web_bp.route("/account/2fa", methods=["GET", "POST"])
@login_required
def account_2fa():
    user_id = g.user["id"]

    conn = get_conn()
    try:
        db_user = users_repo.get_user(conn, user_id)
    finally:
        conn.close()

    totp_enabled = bool(row_value(db_user, "totp_enabled", 0))
    totp_secret = row_value(db_user, "totp_secret", None)


    # If already enabled: show status + backup codes
    if totp_enabled and totp_secret:
        conn = get_conn()
        try:
            codes = backup_codes_repo.list_codes(conn, user_id)
        finally:
            conn.close()

        return render_template(
            "account/2fa.html",
            enabled=True,
            secret=None,
            codes=codes,
        )

    # Not yet enabled → setup flow
    # We store the pending secret in session until user enters a valid TOTP code
    pending_secret = session.get("pending_totp_secret")
    if not pending_secret:
        # Generate a vanilla Base32 secret and normalize it just in case
        raw_secret = pyotp.random_base32()
        # Ensure no whitespace and always uppercase; only A–Z2–7 are used
        pending_secret = raw_secret.strip().replace(" ", "").upper()
        session["pending_totp_secret"] = pending_secret


    totp = pyotp.TOTP(pending_secret)
    otpauth_url = totp.provisioning_uri(name=db_user["email"], issuer_name="Workout tracker")

    if request.method == "POST":
        code = (request.form.get("code") or "").strip()

        if totp.verify(code, valid_window=1):
            # Save secret + mark totp_enabled
            conn = get_conn()
            try:
                users_repo.enable_totp(conn, user_id, pending_secret)
                # Generate (or replace) backup codes
                backup_codes_repo.replace_codes(conn, user_id, count=10)
            finally:
                conn.close()

            session.pop("pending_totp_secret", None)
            flash("Two-factor authentication enabled. Backup codes generated.", "success")
            return redirect(url_for("web.account_2fa"))
        else:
            flash("Invalid code, please try again.", "error")

    return render_template(
        "account/2fa.html",
        enabled=False,
        secret=pending_secret,
        otpauth_url=otpauth_url,
        codes=None,
    )


@web_bp.route("/preferences", methods=["GET", "POST"])
@login_required
def preferences():
    user_id = g.user["id"]

    if request.method == "POST":
        action = request.form.get("action", "")
        conn = get_conn()
        try:
            if action == "week_start":
                week_start = (request.form.get("week_start") or "").strip().lower()
                if week_start not in {"sun", "mon"}:
                    raise ValueError("Week start must be Sunday or Monday.")
                users_repo.update_week_start(conn, user_id, week_start)
                flash("Week start preference updated.", "success")
            else:
                flash("Unknown preference update.", "error")
        except ValueError as exc:
            flash(str(exc), "error")
        finally:
            conn.close()
        return redirect(url_for("web.preferences"))

    conn = get_conn()
    try:
        user = users_repo.get_user(conn, user_id)
    finally:
        conn.close()
    return render_template("account/preferences.html", user=user)


@web_bp.route("/account/muscles", methods=["GET", "POST"])
@login_required
def manage_muscles():
    user_id = g.user["id"]

    conn = get_conn()
    try:
        muscles_repo.ensure_default_muscles(conn, user_id)

        if request.method == "POST":
            action = request.form.get("action", "")

            try:
                if action == "add":
                    name = request.form.get("name", "").strip()
                    color = request.form.get("color", "").strip()
                    muscles_repo.add_muscle(conn, user_id, name, color=color)
                    flash("Muscle group added.", "success")
                elif action == "rename":
                    muscle_id = request.form.get("muscle_id", type=int)
                    new_name = request.form.get("new_name", "").strip()
                    color = request.form.get("color", "").strip()
                    if muscle_id is None:
                        raise ValueError("Invalid muscle selection.")
                    updated_id = muscles_repo.rename_muscle(
                        conn,
                        user_id,
                        muscle_id,
                        new_name,
                        color=color,
                    )
                    if updated_id is None:
                        raise ValueError("Muscle group not found.")
                    flash("Muscle group updated.", "success")
                elif action == "remove":
                    muscle_id = request.form.get("muscle_id", type=int)
                    if muscle_id is None:
                        raise ValueError("Invalid muscle selection.")
                    muscles_repo.deactivate_muscle(conn, user_id, muscle_id)
                    flash("Muscle group removed from your list.", "success")
                elif action == "reset":
                    muscles_repo.reset_to_default(conn, user_id)
                    flash("Muscle groups reset to defaults.", "success")
                else:
                    flash("Unknown action.", "error")
            except ValueError as exc:
                flash(str(exc), "error")

            return redirect(url_for("web.manage_muscles"))

        muscles = muscles_repo.list_muscles(conn, user_id=user_id, active_only=True)
    finally:
        conn.close()

    return render_template("account/muscles.html", muscles=muscles)


@web_bp.route("/login/2fa", methods=["GET", "POST"])
def login_2fa():
    pending_id = session.get("pending_2fa_user_id")
    if not pending_id:
        return redirect(url_for("web.login"))

    conn = get_conn()
    try:
        user = users_repo.get_user(conn, pending_id)
    finally:
        conn.close()

    # Use row_value instead of .get on DB rows
    if user is None or not row_value(user, "totp_secret", None):
        session.pop("pending_2fa_user_id", None)
        return redirect(url_for("web.login"))

    error = None

    if request.method == "POST":
        code = (request.form.get("code") or "").strip()

        # First try TOTP
        totp = pyotp.TOTP(row_value(user, "totp_secret", ""))
        if totp.verify(code, valid_window=1):
            user_obj = make_user(user)
            login_user(user_obj)
            session.pop("pending_2fa_user_id", None)
            flash("Logged in with 2FA.", "success")
            return redirect(url_for("web.workouts_index"))

        # If TOTP fails, try backup codes
        conn = get_conn()
        try:
            if backup_codes_repo.consume_code(conn, user["id"], code):
                user_obj = make_user(user)
                login_user(user_obj)
                session.pop("pending_2fa_user_id", None)
                flash(
                    "Logged in using a backup code. "
                    "This code has been marked as used.",
                    "success",
                )
                return redirect(url_for("web.workouts_index"))
            else:
                error = "Invalid 2FA or backup code."
        finally:
            conn.close()

        if error:
            flash(error, "error")

    return render_template("auth/login_2fa.html")



@web_bp.route("/account/2fa/backup-codes.txt", methods=["GET"])
@login_required
def download_backup_codes():
    user_id = g.user["id"]

    conn = get_conn()
    try:
        codes = backup_codes_repo.list_codes(conn, user_id)
    finally:
        conn.close()

    # Include only unused codes in the file
    code_lines = [row["code"] for row in codes if not row["used"]]

    content_lines = [
        "Your backup codes",
        "=================",
        "",
        *code_lines,
        "",
        "Keep these codes in a safe place. Anyone with these codes can log into your account.",
        "If you lose both your authenticator and these codes, account recovery cannot be guaranteed.",
    ]
    content = "\n".join(content_lines) + "\n"

    return Response(
        content,
        mimetype="text/plain",
        headers={
            "Content-Disposition": 'attachment; filename="backup-codes.txt"'
        },
    )


def _serialize_datetime(value):
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


@web_bp.route("/account/export", methods=["GET"])
@login_required
def export_workouts():
    user_id = g.user["id"]
    options_submitted = request.args.get("export_options") == "1"

    def option_enabled(name: str, default: bool) -> bool:
        if not options_submitted:
            return default
        return (request.args.get(name) or "").lower() in {"1", "true", "on", "yes"}

    conn = get_conn()
    try:
        user = users_repo.get_user(conn, user_id)
        rows = workouts_repo.export_workouts_with_exercises(conn, user_id)
    finally:
        conn.close()

    include_notes = option_enabled("include_notes", True)
    include_weights = option_enabled("include_weights", True)
    include_sets = option_enabled("include_sets", True)
    include_muscles = option_enabled("include_muscles", True)
    include_timestamps = option_enabled("include_timestamps", True)

    workouts = []
    workout_lookup = {}

    for row in rows:
        workout_id = row["workout_id"]
        workout = workout_lookup.get(workout_id)
        if workout is None:
            workout = {
                "id": workout_id,
                "date": _serialize_datetime(row["workout_date"]),
                "exercises": [],
                "_exercise_lookup": {},
            }
            if include_notes:
                workout["notes"] = row["workout_notes"]
            if include_timestamps:
                workout["created_at"] = _serialize_datetime(row["workout_created_at"])
            workout_lookup[workout_id] = workout
            workouts.append(workout)

        exercise_id = row["exercise_id"]
        if exercise_id is None:
            continue

        exercise_lookup = workout["_exercise_lookup"]
        exercise = exercise_lookup.get(exercise_id)
        if exercise is None:
            exercise = {
                "id": exercise_id,
            }
            if include_notes:
                exercise["notes"] = row["exercise_notes"]
            if include_weights:
                exercise["weight_used"] = row["weight_used"]
                exercise["weight_unit"] = row["weight_unit"]
                exercise["weight_used_kg"] = row["weight_used_kg"]
            if include_sets:
                exercise["num_of_sets"] = row["num_of_sets"]
            if include_timestamps:
                exercise["created_at"] = _serialize_datetime(row["exercise_created_at"])
            if include_muscles:
                exercise["muscles"] = []
            exercise_lookup[exercise_id] = exercise
            workout["exercises"].append(exercise)

        muscle_name = row["muscle_name"]
        if include_muscles and muscle_name:
            exercise["muscles"].append(
                {
                    "name": muscle_name,
                    "color": row["muscle_color"],
                }
            )

    for workout in workouts:
        workout.pop("_exercise_lookup", None)

    exported_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "exported_at": exported_at,
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"],
        },
        "workouts": workouts,
    }

    content = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    filename = f"workouts-export-{exported_at[:10]}.json"

    return Response(
        content,
        mimetype="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        },
    )
