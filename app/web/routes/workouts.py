# app/web/routes/workouts.py

from datetime import date as _date, datetime, timedelta

from flask import render_template, abort, g, request

from ...db.connection import get_conn
from ...db.repositories import workouts as workouts_repo
from ...db.repositories import exercises as exercises_repo
from .. import web_bp
from ..auth_utils import login_required


def _ordinal(n: int) -> str:
    """Return 1 -> '1st', 2 -> '2nd', etc."""
    if 11 <= n <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_date(d: _date) -> str:
    """Format a date like 'Nov 13th, 2025'."""
    return f"{d.strftime('%b')} {_ordinal(d.day)}, {d.year}"


def _format_range(start: _date, end: _date) -> str:
    return f"{_format_date(start)} → {_format_date(end)}"


@web_bp.route("/workouts")
@login_required
def workouts_index():
    conn = get_conn()
    try:
        user_id = g.user["id"]
        rows = workouts_repo.list_workouts(conn, user_id=user_id)
    finally:
        conn.close()

    today = _date.today()
    current_week_start = today - timedelta(days=today.weekday())  # Monday
    recent_cutoff = current_week_start - timedelta(weeks=4)       # 4 weeks before this week

    week_groups = {}   # week_start (date) -> [workouts]
    month_groups = {}  # (year, month) -> [workouts]

    for row in rows:
        # row["date"] is "YYYY-MM-DD" (skip if missing for any reason)
        if not row["date"]:
            continue

        raw_date = row["date"]
        if isinstance(raw_date, _date):
            d = raw_date
        else:
            d = datetime.strptime(raw_date, "%Y-%m-%d").date()

        raw_muscles = row["muscles"] or ""
        muscles_display = ""
        if raw_muscles:
            # ensure "back, chest, legs" spacing
            muscles_display = ", ".join(part.strip() for part in raw_muscles.split(","))

        workout = {
            "id": row["id"],
            "date": d,
            "date_display": _format_date(d),
            "muscles": raw_muscles,
            "muscles_display": muscles_display,
        }

        week_start = d - timedelta(days=d.weekday())  # Monday of that week

        if week_start >= recent_cutoff:
            week_groups.setdefault(week_start, []).append(workout)
        else:
            month_key = (d.year, d.month)
            month_groups.setdefault(month_key, []).append(workout)

    # Build ordered week groups (most recent first)
    week_groups_list = []
    for ws in sorted(week_groups.keys(), reverse=True):
        we = ws + timedelta(days=6)
        range_str = _format_range(ws, we)

        if ws == current_week_start:
            label = "This week"
            range_display = range_str
        elif ws == current_week_start - timedelta(weeks=1):
            label = "Last week"
            range_display = range_str
        else:
            label = range_str
            range_display = None  # no separate range line

        week_groups_list.append({
            "label": label,
            "range": range_display,
            "workouts": week_groups[ws],
        })

    # Build ordered month groups (most recent month first)
    month_groups_list = []
    for (year, month) in sorted(month_groups.keys(), reverse=True):
        month_name = datetime(year, month, 1).strftime("%B")  # "November"
        heading = f"{month_name} {year}"
        month_groups_list.append({
            "heading": heading,
            "workouts": month_groups[(year, month)],
        })

    # ✅ Always return a response
    return render_template(
        "workouts/index.html",
        week_groups=week_groups_list,
        month_groups=month_groups_list,
    )


@web_bp.route("/workouts/<int:workout_id>")
@login_required
def workout_detail(workout_id):
    """Show a single workout and its exercises."""
    conn = get_conn()
    try:
        user_id = g.user["id"]
        workout = workouts_repo.get_workout(conn, workout_id, user_id=user_id)
        if workout is None:
            # Either doesn't exist OR doesn't belong to this user
            abort(404)

        exercises = exercises_repo.list_for_workout(conn, workout_id)
    finally:
        conn.close()

    editable = request.args.get("edit") == "1"
    unit_pref = request.args.get("unit", "stored")
    if unit_pref not in {"stored", "converted"}:
        unit_pref = "stored"

    return render_template(
        "workouts/detail.html",
        workout=workout,
        exercises=exercises,
        editable=editable,
        unit_pref=unit_pref,
    )
