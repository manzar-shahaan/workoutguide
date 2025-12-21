# app/db/repositories/workouts.py

from sqlalchemy import text


def list_workouts(conn, user_id: int):
    sql = """
        SELECT
            w.id,
            w.date,
            COALESCE(string_agg(DISTINCT m.name, ','), '') AS muscles
        FROM workout w
        LEFT JOIN exercise e ON e.workout_id = w.id
        LEFT JOIN exercise_muscle em ON em.exercise_id = e.id
        LEFT JOIN muscle m ON m.id = em.muscle_id AND m.user_id = w.user_id
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
            COALESCE(string_agg(DISTINCT m.name, ','), '') AS muscles
        FROM workout w
        LEFT JOIN exercise e ON e.workout_id = w.id
        LEFT JOIN exercise_muscle em ON em.exercise_id = e.id
        LEFT JOIN muscle m ON m.id = em.muscle_id AND m.user_id = w.user_id
        WHERE w.id = :workout_id AND w.user_id = :user_id
        GROUP BY w.id, w.date
    """
    result = conn.execute(text(sql), {"workout_id": workout_id, "user_id": user_id})
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
