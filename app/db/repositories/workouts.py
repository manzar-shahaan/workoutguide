# app/db/repositories/workouts.py

from sqlalchemy import text


def list_workouts(conn, user_id: int):
    sql = """
        SELECT
            w.id,
            w.date,
            COALESCE(string_agg(DISTINCT br.name, ',' ORDER BY br.name), '') AS muscles,
            COALESCE(string_agg(DISTINCT br.name, '||' ORDER BY br.name), '') AS muscle_data
        FROM workout w
        LEFT JOIN exercise e ON e.workout_id = w.id
        LEFT JOIN exercise_catalog_region ecr ON ecr.exercise_catalog_id = e.exercise_catalog_id
        LEFT JOIN body_region br ON br.slug = ecr.region_slug
        WHERE w.user_id = :user_id
        GROUP BY w.id, w.date
        ORDER BY w.date DESC, w.id DESC
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().all()


def get_workout(conn, workout_id: int, user_id: int):
    sql = """
        SELECT
            w.id,
            w.date,
            COALESCE(string_agg(DISTINCT br.name, ',' ORDER BY br.name), '') AS muscles,
            COALESCE(string_agg(DISTINCT br.name, '||' ORDER BY br.name), '') AS muscle_data
        FROM workout w
        LEFT JOIN exercise e ON e.workout_id = w.id
        LEFT JOIN exercise_catalog_region ecr ON ecr.exercise_catalog_id = e.exercise_catalog_id
        LEFT JOIN body_region br ON br.slug = ecr.region_slug
        WHERE w.id = :workout_id AND w.user_id = :user_id
        GROUP BY w.id, w.date
    """
    result = conn.execute(text(sql), {"workout_id": workout_id, "user_id": user_id})
    return result.mappings().fetchone()


def get_most_recent(conn, user_id: int):
    sql = """
        SELECT
            w.id,
            w.date,
            COALESCE(string_agg(DISTINCT br.name, ', ' ORDER BY br.name), '') AS muscles
        FROM workout w
        LEFT JOIN exercise e ON e.workout_id = w.id
        LEFT JOIN exercise_catalog_region ecr ON ecr.exercise_catalog_id = e.exercise_catalog_id
        LEFT JOIN body_region br ON br.slug = ecr.region_slug
        WHERE w.user_id = :user_id
        GROUP BY w.id, w.date
        ORDER BY w.date DESC, w.id DESC
        LIMIT 1
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().fetchone()


def find_by_user_and_date(conn, user_id: int, date: str):
    sql = """
        SELECT id, date, user_id
        FROM workout
        WHERE user_id = :user_id AND date = :date
    """
    result = conn.execute(text(sql), {"user_id": user_id, "date": date})
    return result.mappings().fetchone()


def create_workout(conn, user_id: int, date: str, notes: str | None = None):
    sql = """
        INSERT INTO workout (date, user_id, notes)
        VALUES (:date, :user_id, :notes)
        RETURNING id
    """
    cur = conn.execute(text(sql), {"date": date, "user_id": user_id, "notes": notes})
    conn.commit()
    return cur.scalar_one()


def get_or_create_workout_by_date(
    conn,
    user_id: int,
    date: str,
    notes: str | None = None,
):
    """
    Returns a workout row (id, date, user_id) for this user + date.
    - If it exists already, returns the existing row.
    - If it doesn't, creates it (with optional notes) and returns the new row.
    """
    existing = find_by_user_and_date(conn, user_id, date)
    if existing is not None:
        return existing

    create_workout(conn, user_id=user_id, date=date, notes=notes)
    return find_by_user_and_date(conn, user_id, date)


def delete_workout(conn, workout_id: int, user_id: int):
    sql = "DELETE FROM workout WHERE id = :workout_id AND user_id = :user_id"
    conn.execute(text(sql), {"workout_id": workout_id, "user_id": user_id})
    conn.commit()


def export_workouts_with_exercises(conn, user_id: int):
    sql = """
        SELECT
            w.id AS workout_id,
            w.date AS workout_date,
            w.notes AS workout_notes,
            w.created_at AS workout_created_at,
            e.id AS exercise_id,
            e.notes AS exercise_notes,
            e.weight_used,
            e.weight_unit,
            e.weight_used_kg,
            e.num_of_sets,
            e.avg_reps,
            e.max_reps,
            e.created_at AS exercise_created_at,
            br.name AS muscle_name
        FROM workout w
        LEFT JOIN exercise e ON e.workout_id = w.id
        LEFT JOIN exercise_catalog_region ecr ON ecr.exercise_catalog_id = e.exercise_catalog_id
        LEFT JOIN body_region br ON br.slug = ecr.region_slug
        WHERE w.user_id = :user_id
        ORDER BY w.date DESC, w.id DESC, e.id, ecr.rank
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().all()
