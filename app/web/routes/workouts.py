# app/web/routes/workouts.py

import calendar
from datetime import date as _date, datetime, timedelta

from flask import render_template, abort, g, request, jsonify, url_for

from ...db.connection import get_conn
from ...db.repositories import workouts as workouts_repo
from ...db.repositories import exercises as exercises_repo
from ...db.repositories import stats as stats_repo
from ...db.repositories import exercise_catalog as exercise_catalog_repo
from ...db.repositories import freshness as freshness_repo
from .. import web_bp
from ..auth_utils import login_required
from utils.date_utils import format_date
from utils.freshness import compute_effective_days, most_overdue_regions
from utils.body_regions import REGIONS, REGION_SLUGS

WEEKDAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _format_range(start: _date, end: _date) -> str:
    return f"{format_date(start)} → {format_date(end)}"


def _parse_muscle_data(raw_data: str) -> list[dict]:
    """Body-region names tagged on an exercise/workout, in the order the SQL provided."""
    if not raw_data:
        return []
    items = []
    for part in raw_data.split("||"):
        name = part.strip()
        if not name:
            continue
        items.append({"name": name})
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

        most_recent_workout = workouts_repo.get_most_recent(conn, user_id=user_id)

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

        last_trained = freshness_repo.last_trained_by_region(conn, user_id=user_id)
    finally:
        conn.close()

    today = _date.today()
    effective_days = compute_effective_days(last_trained, today)
    overdue_regions = most_overdue_regions(effective_days)

    current_week_start = today - timedelta(days=today.weekday())  # Monday
    recent_cutoff = current_week_start - timedelta(weeks=4)       # 4 weeks before this week

    last_workout = None
    if most_recent_workout is not None and most_recent_workout["date"]:
        raw_date = most_recent_workout["date"]
        d = raw_date if isinstance(raw_date, _date) else datetime.strptime(raw_date, "%Y-%m-%d").date()
        last_workout = {
            "id": most_recent_workout["id"],
            "weekday": d.strftime("%a"),
            "date_display": format_date(d),
            "muscles_display": most_recent_workout["muscles"] or None,
        }

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
                    "avg_reps": row.get("avg_reps"),
                    "max_reps": row.get("max_reps"),
                    "date": d,
                    "date_display": format_date(d),
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
                "date_display": format_date(d),
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
        last_workout=last_workout,
        overdue_regions=overdue_regions,
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
        exercise_sets = {
            ex["id"]: exercises_repo.get_sets_for_exercise(conn, ex["id"]) for ex in exercises
        }
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
        sets = exercise_sets.get(ex["id"], [])
        formatted["sets"] = sets
        formatted["volume_kg"] = sum(
            s["weight_used_kg"] * s["reps"]
            for s in sets
            if s["weight_used_kg"] is not None and s["reps"] is not None
        )
        formatted["volume_stored"] = sum(
            s["weight_used"] * s["reps"]
            for s in sets
            if s["weight_used"] is not None and s["reps"] is not None
        )
        formatted["has_volume"] = any(
            s["weight_used_kg"] is not None and s["reps"] is not None for s in sets
        )
        formatted_exercises.append(formatted)

    editable = request.args.get("edit") == "1"
    unit_pref = request.args.get("unit", "stored")
    if unit_pref not in {"stored", "converted"}:
        unit_pref = "stored"

    raw_date = workout["date"]
    workout_date_obj = (
        raw_date if isinstance(raw_date, _date) else datetime.strptime(raw_date, "%Y-%m-%d").date()
    )
    workout_date_display = format_date(workout_date_obj)

    # Session volume total: always in the user's preferred unit, computed
    # from weight_used_kg so mixed lb/kg entries sum correctly. Unlike the
    # per-row weight display, this doesn't follow the stored/converted
    # toggle -- "converted" flips each row to *its own* opposite unit, which
    # has no single consistent meaning to sum across rows.
    session_volume_kg = 0.0
    has_volume = False
    for ex in formatted_exercises:
        if ex["has_volume"]:
            session_volume_kg += ex["volume_kg"]
            has_volume = True

    session_volume_unit = g.user.get("weight_unit") or "lb"
    session_volume = None
    if has_volume:
        session_volume = (
            session_volume_kg / 0.45359237 if session_volume_unit == "lb" else session_volume_kg
        )

    return render_template(
        "workouts/detail.html",
        workout=workout,
        workout_date_display=workout_date_display,
        workout_muscles=workout_muscles,
        exercises=formatted_exercises,
        editable=editable,
        unit_pref=unit_pref,
        session_volume=session_volume,
        session_volume_unit=session_volume_unit,
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

        totals = stats_repo.totals(conn, user_id=user_id)
    finally:
        conn.close()

    muscles = [{"id": slug, "name": name} for slug, name, _view in REGIONS]

    week_anchor = _start_of_week(anchor_date, week_start_pref)
    week_prev_date = week_anchor - timedelta(days=7)
    week_next_date = week_anchor + timedelta(days=7)
    month_prev_date = _shift_months(anchor_date, -1)
    month_next_date = _shift_months(anchor_date, 1)

    chart_muscle = request.args.get("region")
    if chart_muscle not in REGION_SLUGS:
        chart_muscle = muscles[0]["id"] if muscles else None
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
    chart_metric = request.args.get("metric", "weight")
    if chart_metric not in {"weight", "avg_reps", "max_reps", "volume"}:
        chart_metric = "weight"
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
            rows = exercise_catalog_repo.list_for_region(
                conn,
                user_id=user_id,
                region_slug=chart_muscle,
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
                    exercise_ids=chart_exercise_ids,
                    start_date=chart_start,
                    end_date=chart_end,
                    metric=chart_metric,
                )
            elif chart_exercise:
                rows = stats_repo.exercise_progression(
                    conn,
                    user_id=user_id,
                    exercise_id=chart_exercise,
                    start_date=chart_start,
                    end_date=chart_end,
                    metric=chart_metric,
                )
            else:
                rows = stats_repo.region_progression(
                    conn,
                    user_id=user_id,
                    region_slug=chart_muscle,
                    start_date=chart_start,
                    end_date=chart_end,
                    metric=chart_metric,
                )
        finally:
            conn.close()
        chart_data = {
            "labels": [row["date"].strftime("%Y-%m-%d") for row in rows],
            "values": [float(row["value"]) for row in rows],
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
        totals=totals,
        muscles=muscles,
        exercise_options=exercise_options,
        weekdays=_weekdays_for_start(week_start_pref),
        chart_muscle=chart_muscle,
        chart_exercise=chart_exercise,
        chart_exercise_ids=chart_exercise_ids,
        chart_range=chart_range,
        chart_metric=chart_metric,
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
    region_slug = request.args.get("region")
    exercise_ids_raw = request.args.get("exercise_ids")
    exercise_id = request.args.get("exercise_id", type=int)
    range_key = request.args.get("range", "last_3_months")
    metric = request.args.get("metric", "weight")
    start_raw = request.args.get("start")
    end_raw = request.args.get("end")

    if region_slug not in REGION_SLUGS:
        return jsonify({"labels": [], "values": []})
    if metric not in {"weight", "avg_reps", "max_reps", "volume"}:
        metric = "weight"

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
                exercise_ids=exercise_ids,
                start_date=range_start,
                end_date=range_end,
                metric=metric,
            )
        else:
            rows = stats_repo.region_progression(
                conn,
                user_id=user_id,
                region_slug=region_slug,
                start_date=range_start,
                end_date=range_end,
                metric=metric,
            )
    finally:
        conn.close()

    return jsonify(
        {
            "labels": [row["date"].strftime("%Y-%m-%d") for row in rows],
            "values": [float(row["value"]) for row in rows],
        }
    )


@web_bp.route("/stats/exercise-options")
@login_required
def stats_exercise_options():
    user_id = g.user["id"]
    region_slug = request.args.get("region")
    if region_slug not in REGION_SLUGS:
        return jsonify({"items": []})

    conn = get_conn()
    try:
        rows = exercise_catalog_repo.list_for_region(
            conn,
            user_id=user_id,
            region_slug=region_slug,
        )
    finally:
        conn.close()

    items = [{"id": row["id"], "name": row["name"]} for row in rows]
    return jsonify({"items": items})
