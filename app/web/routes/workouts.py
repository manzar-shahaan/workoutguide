# app/web/routes/workouts.py

import calendar
import re
from datetime import date as _date, datetime, timedelta

from flask import render_template, abort, g, request, jsonify, url_for

from ...db.connection import get_conn
from ...db.repositories import workouts as workouts_repo
from ...db.repositories import exercises as exercises_repo
from ...db.repositories import muscles as muscles_repo
from ...db.repositories import stats as stats_repo
from ...db.repositories import exercise_catalog as exercise_catalog_repo
from .. import web_bp
from ..auth_utils import login_required

DEFAULT_MUSCLE_COLOR = "#64748b"
COLOR_REGEX = re.compile(r"^#[0-9a-fA-F]{6}$")
WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


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


def _parse_muscle_data(raw_data: str) -> list[dict]:
    if not raw_data:
        return []
    items = []
    for part in raw_data.split("||"):
        if not part:
            continue
        if "::" in part:
            name, color = part.split("::", 1)
        else:
            name, color = part, ""
        name = name.strip()
        if not name:
            continue
        color = (color or DEFAULT_MUSCLE_COLOR).strip()
        if not COLOR_REGEX.match(color):
            color = DEFAULT_MUSCLE_COLOR
        items.append({"name": name, "color": color})
    items.sort(key=lambda item: item["name"])
    return items


def _format_muscle_list(raw_muscles: str) -> str:
    if not raw_muscles:
        return ""
    return ", ".join(part.strip() for part in raw_muscles.split(",") if part.strip())


def _build_daily_lookup(rows):
    lookup = {}
    for row in rows:
        raw_date = row["date"]
        if not raw_date:
            continue
        day = raw_date if isinstance(raw_date, _date) else datetime.strptime(raw_date, "%Y-%m-%d").date()
        muscle_data = row["muscle_data"] if "muscle_data" in row.keys() else ""
        lookup[day] = {
            "count": row["exercise_count"] or 0,
            "muscles": _parse_muscle_data(muscle_data),
        }
    return lookup


def _week_start_index(week_start: str) -> int:
    return 6 if week_start == "sun" else 0


def _weekdays_for_start(week_start: str) -> list[str]:
    index = _week_start_index(week_start)
    return WEEKDAY_LABELS[index:] + WEEKDAY_LABELS[:index]


def _start_of_week(day: _date, week_start: str) -> _date:
    firstweekday = _week_start_index(week_start)
    offset = (day.weekday() - firstweekday) % 7
    return day - timedelta(days=offset)


def _build_month_calendar(anchor_date: _date, daily_lookup: dict, week_start: str) -> dict:
    year = anchor_date.year
    month = anchor_date.month
    cal = calendar.Calendar(firstweekday=_week_start_index(week_start))
    weeks = []
    month_total = 0
    for week in cal.monthdatescalendar(year, month):
        days = []
        week_total = 0
        for day in week:
            info = daily_lookup.get(day, {"count": 0, "muscles": []})
            week_total += info["count"]
            days.append({
                "date": day,
                "in_month": day.month == month,
                "count": info["count"],
                "muscles": info["muscles"],
            })
        month_total += week_total
        weeks.append({"days": days, "total": week_total})
    return {
        "weeks": weeks,
        "label": anchor_date.strftime("%B %Y"),
        "month_total": month_total,
    }


def _build_week_calendar(anchor_date: _date, daily_lookup: dict, week_start: str) -> dict:
    week_start = _start_of_week(anchor_date, week_start)
    days = []
    week_total = 0
    for i in range(7):
        day = week_start + timedelta(days=i)
        info = daily_lookup.get(day, {"count": 0, "muscles": []})
        week_total += info["count"]
        days.append({
            "date": day,
            "count": info["count"],
            "muscles": info["muscles"],
        })
    return {
        "week_start": week_start,
        "week_end": week_start + timedelta(days=6),
        "days": days,
        "week_total": week_total,
    }


def _shift_months(date_value: _date, months: int) -> _date:
    year = date_value.year + (date_value.month - 1 + months) // 12
    month = (date_value.month - 1 + months) % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(date_value.day, last_day)
    return _date(year, month, day)


def _range_bounds(range_key: str, today: _date) -> tuple[_date, _date]:
    if range_key == "last_week":
        return today - timedelta(days=6), today
    if range_key == "last_month":
        return _shift_months(today, -1), today
    if range_key == "last_3_months":
        return _shift_months(today, -3), today
    if range_key == "last_6_months":
        return _shift_months(today, -6), today
    if range_key == "last_year":
        return _shift_months(today, -12), today
    if range_key == "last_2_years":
        return _shift_months(today, -24), today
    return today - timedelta(days=30), today


@web_bp.route("/workouts")
@login_required
def workouts_index():
    search_query = (request.args.get("q") or "").strip()
    search_results = []

    conn = get_conn()
    try:
        user_id = g.user["id"]
        if search_query:
            exercise_rows = exercises_repo.search_exercises(
                conn,
                user_id=user_id,
                query=search_query,
            )
        else:
            rows = workouts_repo.list_workouts(conn, user_id=user_id)

        week_start_pref = g.user.get("week_start", "sun")
        month_anchor = _date.today()
        month_start = month_anchor.replace(day=1)
        month_last_day = calendar.monthrange(month_anchor.year, month_anchor.month)[1]
        month_end = month_anchor.replace(day=month_last_day)
        daily_rows = stats_repo.exercise_activity_by_day(
            conn,
            user_id=user_id,
            start_date=month_start,
            end_date=month_end,
        )
        daily_lookup = _build_daily_lookup(daily_rows)
        month_calendar = _build_month_calendar(month_anchor, daily_lookup, week_start_pref)
    finally:
        conn.close()

    today = _date.today()
    current_week_start = today - timedelta(days=today.weekday())  # Monday
    recent_cutoff = current_week_start - timedelta(weeks=4)       # 4 weeks before this week

    week_groups = {}   # week_start (date) -> [workouts]
    month_groups = {}  # (year, month) -> [workouts]

    if search_query:
        for row in exercise_rows:
            raw_date = row["workout_date"]
            if not raw_date:
                continue
            if isinstance(raw_date, _date):
                d = raw_date
            else:
                d = datetime.strptime(raw_date, "%Y-%m-%d").date()

            muscle_data = row["muscle_data"] if "muscle_data" in row.keys() else ""
            muscles_list = _parse_muscle_data(muscle_data)

            search_results.append(
                {
                    "id": row["id"],
                    "workout_id": row["workout_id"],
                    "notes": row["notes"],
                    "exercise_name": row.get("exercise_name"),
                    "weight_used": row["weight_used"],
                    "weight_unit": row["weight_unit"],
                    "num_of_sets": row["num_of_sets"],
                    "date": d,
                    "date_display": _format_date(d),
                    "weekday": d.strftime("%a"),
                    "muscles_list": muscles_list,
                }
            )
    else:
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
            muscles_display = _format_muscle_list(raw_muscles)
            muscle_data = row["muscle_data"] if "muscle_data" in row.keys() else ""
            muscles_list = _parse_muscle_data(muscle_data)

            workout = {
                "id": row["id"],
                "date": d,
                "date_display": _format_date(d),
                "muscles": raw_muscles,
                "muscles_display": muscles_display,
                "muscles_list": muscles_list,
            }

            week_start = d - timedelta(days=d.weekday())  # Monday of that week

            if week_start >= recent_cutoff:
                week_groups.setdefault(week_start, []).append(workout)
            else:
                month_key = (d.year, d.month)
                month_groups.setdefault(month_key, []).append(workout)

    # Build ordered week groups (most recent first)
    week_groups_list = []
    if not search_query:
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
    if not search_query:
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
        stats_month_calendar=month_calendar,
        stats_month_anchor=month_anchor,
        stats_weekdays=_weekdays_for_start(week_start_pref),
        search_query=search_query,
        search_results=search_results,
        today=today,
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

    workout_muscles = _parse_muscle_data(
        workout["muscle_data"] if "muscle_data" in workout.keys() else ""
    )

    formatted_exercises = []
    for ex in exercises:
        muscle_list = _parse_muscle_data(
            ex["muscle_data"] if "muscle_data" in ex.keys() else ""
        )
        formatted = dict(ex)
        formatted["muscles_list"] = muscle_list
        formatted_exercises.append(formatted)

    editable = request.args.get("edit") == "1"
    unit_pref = request.args.get("unit", "stored")
    if unit_pref not in {"stored", "converted"}:
        unit_pref = "stored"

    raw_date = workout["date"]
    workout_date_obj = (
        raw_date if isinstance(raw_date, _date) else datetime.strptime(raw_date, "%Y-%m-%d").date()
    )
    workout_date_display = _format_date(workout_date_obj)

    return render_template(
        "workouts/detail.html",
        workout=workout,
        workout_date_display=workout_date_display,
        workout_muscles=workout_muscles,
        exercises=formatted_exercises,
        editable=editable,
        unit_pref=unit_pref,
    )


@web_bp.route("/stats")
@login_required
def stats_index():
    user_id = g.user["id"]
    week_start_pref = g.user.get("week_start", "sun")
    view = request.args.get("view", "month")
    if view not in {"month", "week"}:
        view = "month"

    anchor_raw = request.args.get("date")
    try:
        anchor_date = (
            datetime.strptime(anchor_raw, "%Y-%m-%d").date()
            if anchor_raw
            else _date.today()
        )
    except ValueError:
        anchor_date = _date.today()

    if view == "month":
        range_start = anchor_date.replace(day=1)
        month_last_day = calendar.monthrange(anchor_date.year, anchor_date.month)[1]
        range_end = anchor_date.replace(day=month_last_day)
    else:
        range_start = _start_of_week(anchor_date, week_start_pref)
        range_end = range_start + timedelta(days=6)

    conn = get_conn()
    try:
        daily_rows = stats_repo.exercise_activity_by_day(
            conn,
            user_id=user_id,
            start_date=range_start,
            end_date=range_end,
        )
        daily_lookup = _build_daily_lookup(daily_rows)
        month_calendar = _build_month_calendar(anchor_date, daily_lookup, week_start_pref)
        week_calendar = _build_week_calendar(anchor_date, daily_lookup, week_start_pref)

        week_totals = stats_repo.exercise_counts_by_week(
            conn,
            user_id=user_id,
            week_start=week_start_pref,
        )
        month_totals = stats_repo.exercise_counts_by_month(conn, user_id=user_id)
        totals = stats_repo.totals(conn, user_id=user_id)

        muscles = muscles_repo.list_muscles(conn, user_id=user_id, active_only=True)
    finally:
        conn.close()

    week_anchor = _start_of_week(anchor_date, week_start_pref)
    week_prev_date = week_anchor - timedelta(days=7)
    week_next_date = week_anchor + timedelta(days=7)
    month_prev_date = _shift_months(anchor_date, -1)
    month_next_date = _shift_months(anchor_date, 1)

    chart_muscle = request.args.get("muscle_id", type=int)
    if muscles:
        muscle_ids = {m["id"] for m in muscles}
        if chart_muscle not in muscle_ids:
            chart_muscle = muscles[0]["id"]
    else:
        chart_muscle = None
    chart_exercise_ids_raw = request.args.get("exercise_ids")
    chart_exercise_ids: list[int] = []
    if chart_exercise_ids_raw:
        try:
            chart_exercise_ids = [
                int(value)
                for value in chart_exercise_ids_raw.split(",")
                if value.strip()
            ]
        except ValueError:
            chart_exercise_ids = []
    chart_exercise = request.args.get("exercise_id", type=int)
    chart_range = request.args.get("range", "last_3_months")
    if chart_range not in {
        "last_week",
        "last_month",
        "last_3_months",
        "last_6_months",
        "last_year",
        "last_2_years",
        "custom",
    }:
        chart_range = "last_3_months"

    today = _date.today()
    chart_start, chart_end = _range_bounds(chart_range, today)
    custom_start_default = today - timedelta(days=30)
    exercise_options = []
    if chart_muscle:
        conn = get_conn()
        try:
            rows = exercise_catalog_repo.list_for_muscle(
                conn,
                user_id=user_id,
                muscle_id=chart_muscle,
            )
            exercise_options = [{"id": row["id"], "name": row["name"]} for row in rows]
        finally:
            conn.close()
        exercise_ids_set = {row["id"] for row in exercise_options}
        if chart_exercise_ids:
            chart_exercise_ids = [ex_id for ex_id in chart_exercise_ids if ex_id in exercise_ids_set]
        if chart_exercise is not None and chart_exercise not in exercise_ids_set:
            chart_exercise = None

    chart_data = {"labels": [], "values": []}
    if chart_muscle:
        conn = get_conn()
        try:
            if chart_exercise_ids:
                rows = stats_repo.exercise_progression_multi(
                    conn,
                    user_id=user_id,
                    muscle_id=chart_muscle,
                    exercise_ids=chart_exercise_ids,
                    start_date=chart_start,
                    end_date=chart_end,
                )
            elif chart_exercise:
                rows = stats_repo.exercise_progression(
                    conn,
                    user_id=user_id,
                    exercise_id=chart_exercise,
                    start_date=chart_start,
                    end_date=chart_end,
                )
            else:
                rows = stats_repo.muscle_progression(
                    conn,
                    user_id=user_id,
                    muscle_id=chart_muscle,
                    start_date=chart_start,
                    end_date=chart_end,
                )
        finally:
            conn.close()
        chart_data = {
            "labels": [row["date"].strftime("%Y-%m-%d") for row in rows],
            "values": [float(row["max_weight_kg"]) for row in rows],
        }

    return render_template(
        "stats/index.html",
        view=view,
        anchor_date=anchor_date,
        month_calendar=month_calendar,
        week_calendar=week_calendar,
        week_prev_date=week_prev_date,
        week_next_date=week_next_date,
        month_prev_date=month_prev_date,
        month_next_date=month_next_date,
        week_totals=week_totals,
        month_totals=month_totals,
        totals=totals,
        muscles=muscles,
        exercise_options=exercise_options,
        weekdays=_weekdays_for_start(week_start_pref),
        chart_muscle=chart_muscle,
        chart_exercise=chart_exercise,
        chart_exercise_ids=chart_exercise_ids,
        chart_range=chart_range,
        chart_data=chart_data,
        preferred_unit=g.user.get("weight_unit", "lb"),
        custom_start_default=custom_start_default,
        custom_end_default=today,
        today=today,
    )


@web_bp.route("/stats/muscle-data")
@login_required
def stats_muscle_data():
    user_id = g.user["id"]
    muscle_id = request.args.get("muscle_id", type=int)
    exercise_ids_raw = request.args.get("exercise_ids")
    exercise_id = request.args.get("exercise_id", type=int)
    range_key = request.args.get("range", "last_3_months")
    start_raw = request.args.get("start")
    end_raw = request.args.get("end")

    if muscle_id is None:
        return jsonify({"labels": [], "values": []})

    today = _date.today()
    if range_key == "custom" and start_raw and end_raw:
        try:
            range_start = datetime.strptime(start_raw, "%Y-%m-%d").date()
            range_end = datetime.strptime(end_raw, "%Y-%m-%d").date()
            if range_start > range_end:
                range_start, range_end = range_end, range_start
        except ValueError:
            range_start, range_end = _range_bounds("last_3_months", today)
    else:
        range_start, range_end = _range_bounds(range_key, today)

    exercise_ids: list[int] = []
    if exercise_ids_raw:
        try:
            exercise_ids = [int(value) for value in exercise_ids_raw.split(",") if value.strip()]
        except ValueError:
            exercise_ids = []
    elif exercise_id:
        exercise_ids = [exercise_id]

    conn = get_conn()
    try:
        if exercise_ids:
            rows = stats_repo.exercise_progression_multi(
                conn,
                user_id=user_id,
                muscle_id=muscle_id,
                exercise_ids=exercise_ids,
                start_date=range_start,
                end_date=range_end,
            )
        else:
            rows = stats_repo.muscle_progression(
                conn,
                user_id=user_id,
                muscle_id=muscle_id,
                start_date=range_start,
                end_date=range_end,
            )
    finally:
        conn.close()

    return jsonify(
        {
            "labels": [row["date"].strftime("%Y-%m-%d") for row in rows],
            "values": [float(row["max_weight_kg"]) for row in rows],
        }
    )


@web_bp.route("/stats/exercise-options")
@login_required
def stats_exercise_options():
    user_id = g.user["id"]
    muscle_id = request.args.get("muscle_id", type=int)
    if muscle_id is None:
        return jsonify({"items": []})

    conn = get_conn()
    try:
        muscle = muscles_repo.get_muscle(conn, user_id, muscle_id)
        if muscle is None:
            return jsonify({"items": []})
        rows = exercise_catalog_repo.list_for_muscle(
            conn,
            user_id=user_id,
            muscle_id=muscle_id,
        )
    finally:
        conn.close()

    items = [{"id": row["id"], "name": row["name"]} for row in rows]
    return jsonify({"items": items})
