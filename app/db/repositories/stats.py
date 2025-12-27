# app/db/repositories/stats.py

from sqlalchemy import text


def exercise_activity_by_day(conn, user_id: int, start_date, end_date):
    sql = """
        SELECT
            w.date,
            COUNT(DISTINCT e.id) AS exercise_count,
            COALESCE(
                string_agg(
                    DISTINCT (m.name || '::' || COALESCE(m.color, '')),
                    '||'
                ),
                ''
            ) AS muscle_data
        FROM workout w
        LEFT JOIN exercise e ON e.workout_id = w.id
        LEFT JOIN exercise_muscle em ON em.exercise_id = e.id
        LEFT JOIN muscle m ON m.id = em.muscle_id AND m.user_id = w.user_id
        WHERE w.user_id = :user_id
          AND w.date BETWEEN :start_date AND :end_date
          AND w.date IS NOT NULL
        GROUP BY w.date
        ORDER BY w.date
    """
    result = conn.execute(
        text(sql),
        {
            "user_id": user_id,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    return result.mappings().all()


def exercise_counts_by_week(conn, user_id: int, week_start: str = "mon"):
    if week_start == "sun":
        week_expr = "date_trunc('week', w.date + interval '1 day') - interval '1 day'"
    else:
        week_expr = "date_trunc('week', w.date)"

    sql = f"""
        SELECT
            ({week_expr})::date AS week_start,
            COUNT(e.id) AS exercise_count
        FROM workout w
        LEFT JOIN exercise e ON e.workout_id = w.id
        WHERE w.user_id = :user_id
          AND w.date IS NOT NULL
        GROUP BY week_start
        ORDER BY week_start DESC
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().all()


def exercise_counts_by_month(conn, user_id: int):
    sql = """
        SELECT
            date_trunc('month', w.date)::date AS month_start,
            COUNT(e.id) AS exercise_count
        FROM workout w
        LEFT JOIN exercise e ON e.workout_id = w.id
        WHERE w.user_id = :user_id
          AND w.date IS NOT NULL
        GROUP BY month_start
        ORDER BY month_start DESC
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().all()


def muscle_progression(conn, user_id: int, muscle_id: int, start_date, end_date):
    sql = """
        SELECT
            w.date,
            MAX(
                COALESCE(
                    e.weight_used_kg,
                    CASE
                        WHEN e.weight_unit = 'lb' THEN e.weight_used * 0.45359237
                        WHEN e.weight_unit = 'kg' THEN e.weight_used
                        ELSE NULL
                    END
                )
            ) AS max_weight_kg
        FROM workout w
        JOIN exercise e ON e.workout_id = w.id
        JOIN exercise_muscle em ON em.exercise_id = e.id
        WHERE w.user_id = :user_id
          AND em.muscle_id = :muscle_id
          AND (
            e.weight_used_kg IS NOT NULL
            OR (e.weight_used IS NOT NULL AND e.weight_unit IN ('lb', 'kg'))
          )
          AND w.date BETWEEN :start_date AND :end_date
          AND w.date IS NOT NULL
        GROUP BY w.date
        ORDER BY w.date
    """
    result = conn.execute(
        text(sql),
        {
            "user_id": user_id,
            "muscle_id": muscle_id,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    return result.mappings().all()


def exercise_progression(conn, user_id: int, exercise_id: int, start_date, end_date):
    sql = """
        SELECT
            w.date,
            MAX(
                COALESCE(
                    e.weight_used_kg,
                    CASE
                        WHEN e.weight_unit = 'lb' THEN e.weight_used * 0.45359237
                        WHEN e.weight_unit = 'kg' THEN e.weight_used
                        ELSE NULL
                    END
                )
            ) AS max_weight_kg
        FROM workout w
        JOIN exercise e ON e.workout_id = w.id
        WHERE w.user_id = :user_id
          AND e.exercise_catalog_id = :exercise_id
          AND (
            e.weight_used_kg IS NOT NULL
            OR (e.weight_used IS NOT NULL AND e.weight_unit IN ('lb', 'kg'))
          )
          AND w.date BETWEEN :start_date AND :end_date
          AND w.date IS NOT NULL
        GROUP BY w.date
        ORDER BY w.date
    """
    result = conn.execute(
        text(sql),
        {
            "user_id": user_id,
            "exercise_id": exercise_id,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    return result.mappings().all()


def exercise_progression_multi(
    conn,
    user_id: int,
    muscle_id: int,
    exercise_ids: list[int],
    start_date,
    end_date,
):
    if not exercise_ids:
        return []
    sql = """
        SELECT
            w.date,
            MAX(
                COALESCE(
                    e.weight_used_kg,
                    CASE
                        WHEN e.weight_unit = 'lb' THEN e.weight_used * 0.45359237
                        WHEN e.weight_unit = 'kg' THEN e.weight_used
                        ELSE NULL
                    END
                )
            ) AS max_weight_kg
        FROM workout w
        JOIN exercise e ON e.workout_id = w.id
        JOIN exercise_catalog ec ON ec.id = e.exercise_catalog_id
        WHERE w.user_id = :user_id
          AND ec.user_id = :user_id
          AND ec.muscle_id = :muscle_id
          AND e.exercise_catalog_id = ANY(:exercise_ids)
          AND (
            e.weight_used_kg IS NOT NULL
            OR (e.weight_used IS NOT NULL AND e.weight_unit IN ('lb', 'kg'))
          )
          AND w.date BETWEEN :start_date AND :end_date
          AND w.date IS NOT NULL
        GROUP BY w.date
        ORDER BY w.date
    """
    result = conn.execute(
        text(sql),
        {
            "user_id": user_id,
            "muscle_id": muscle_id,
            "exercise_ids": exercise_ids,
            "start_date": start_date,
            "end_date": end_date,
        },
    )
    return result.mappings().all()


def totals(conn, user_id: int):
    workout_count = conn.execute(
        text("SELECT COUNT(*) AS count FROM workout WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).mappings().fetchone()
    exercise_count = conn.execute(
        text(
            """
            SELECT COUNT(*) AS count
            FROM exercise e
            JOIN workout w ON w.id = e.workout_id
            WHERE w.user_id = :user_id
            """
        ),
        {"user_id": user_id},
    ).mappings().fetchone()
    muscle_count = conn.execute(
        text(
            "SELECT COUNT(*) AS count FROM muscle WHERE user_id = :user_id AND active = TRUE"
        ),
        {"user_id": user_id},
    ).mappings().fetchone()
    last_workout = conn.execute(
        text("SELECT MAX(date) AS date FROM workout WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).mappings().fetchone()
    first_workout = conn.execute(
        text("SELECT MIN(date) AS date FROM workout WHERE user_id = :user_id"),
        {"user_id": user_id},
    ).mappings().fetchone()

    muscle_counts = conn.execute(
        text(
            """
            SELECT
                m.name,
                m.color,
                COUNT(e.id) AS exercise_count
            FROM muscle m
            JOIN exercise_muscle em ON em.muscle_id = m.id
            JOIN exercise e ON e.id = em.exercise_id
            JOIN workout w ON w.id = e.workout_id
            WHERE w.user_id = :user_id
            GROUP BY m.name, m.color
            ORDER BY exercise_count DESC, m.name
            """
        ),
        {"user_id": user_id},
    ).mappings().all()

    month_counts = []
    if first_workout and last_workout and first_workout["date"] and last_workout["date"]:
        month_counts = conn.execute(
            text(
                """
                SELECT
                    months.month_start,
                    COUNT(e.id) AS exercise_count
                FROM (
                    SELECT generate_series(
                        date_trunc('month', :start_date)::date,
                        date_trunc('month', :end_date)::date,
                        interval '1 month'
                    )::date AS month_start
                ) AS months
                LEFT JOIN workout w
                  ON w.user_id = :user_id
                 AND date_trunc('month', w.date)::date = months.month_start
                LEFT JOIN exercise e ON e.workout_id = w.id
                GROUP BY months.month_start
                ORDER BY months.month_start
                """
            ),
            {
                "user_id": user_id,
                "start_date": first_workout["date"],
                "end_date": last_workout["date"],
            },
        ).mappings().all()

    most_targeted = []
    least_targeted = []
    if muscle_counts:
        max_count = muscle_counts[0]["exercise_count"]
        min_count = min(row["exercise_count"] for row in muscle_counts)
        most_targeted = [row for row in muscle_counts if row["exercise_count"] == max_count]
        least_targeted = [row for row in muscle_counts if row["exercise_count"] == min_count]

    most_active_month = []
    least_active_month = []
    if month_counts:
        max_month = max(row["exercise_count"] for row in month_counts)
        min_month = min(row["exercise_count"] for row in month_counts)
        most_active_month = [row for row in month_counts if row["exercise_count"] == max_month]
        least_active_month = [row for row in month_counts if row["exercise_count"] == min_month]

    return {
        "workouts": workout_count["count"] if workout_count else 0,
        "exercises": exercise_count["count"] if exercise_count else 0,
        "muscles": muscle_count["count"] if muscle_count else 0,
        "last_workout": last_workout["date"] if last_workout else None,
        "first_workout": first_workout["date"] if first_workout else None,
        "most_targeted": most_targeted,
        "least_targeted": least_targeted,
        "most_active_month": most_active_month,
        "least_active_month": least_active_month,
    }
