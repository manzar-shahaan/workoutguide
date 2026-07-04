# app/db/repositories/exercises.py

from sqlalchemy import text


def get_sets_for_exercise(conn, exercise_id: int):
    sql = """
        SELECT set_index, weight_used, weight_unit, weight_used_kg, reps
        FROM exercise_set
        WHERE exercise_id = :exercise_id
        ORDER BY set_index
    """
    result = conn.execute(text(sql), {"exercise_id": exercise_id})
    return result.mappings().all()


def _replace_sets(conn, exercise_id: int, sets: list[dict] | None) -> None:
    """
    sets: [{"weight_used": float|None, "weight_unit": str|None,
             "weight_used_kg": float|None, "reps": int|None}, ...]
    Full replace -- simpler and safer than diffing for a handful of rows
    per exercise, and this always runs inside the caller's transaction.
    """
    if sets is None:
        return
    conn.execute(
        text("DELETE FROM exercise_set WHERE exercise_id = :exercise_id"),
        {"exercise_id": exercise_id},
    )
    for index, set_row in enumerate(sets, start=1):
        conn.execute(
            text(
                """
                INSERT INTO exercise_set
                    (exercise_id, set_index, weight_used, weight_unit, weight_used_kg, reps)
                VALUES (:exercise_id, :set_index, :weight_used, :weight_unit, :weight_used_kg, :reps)
                """
            ),
            {
                "exercise_id": exercise_id,
                "set_index": index,
                "weight_used": set_row.get("weight_used"),
                "weight_unit": set_row.get("weight_unit"),
                "weight_used_kg": set_row.get("weight_used_kg"),
                "reps": set_row.get("reps"),
            },
        )

def list_for_workout(conn, workout_id: int):
    sql = """
        SELECT
            e.id,
            e.notes,
            e.exercise_catalog_id,
            e.exercise_name,
            e.weight_used,
            e.weight_unit,
            e.weight_used_kg,
            e.num_of_sets,
            e.avg_reps,
            e.max_reps,
            COALESCE(string_agg(DISTINCT m.name, ','), '') AS muscles,
            COALESCE(
                string_agg(
                    DISTINCT (m.name || '::' || COALESCE(m.color, '')),
                    '||'
                ),
                ''
            ) AS muscle_data
        FROM exercise e
        JOIN workout w ON w.id = e.workout_id
        LEFT JOIN exercise_muscle em ON em.exercise_id = e.id
        LEFT JOIN muscle m ON m.id = em.muscle_id AND m.user_id = w.user_id
        WHERE e.workout_id = :workout_id
        GROUP BY e.id, e.notes, e.exercise_catalog_id, e.exercise_name,
                 e.weight_used, e.weight_unit, e.weight_used_kg, e.num_of_sets,
                 e.avg_reps, e.max_reps
        ORDER BY e.id
    """
    result = conn.execute(text(sql), {"workout_id": workout_id})
    return result.mappings().all()


def search_exercises(conn, user_id: int, query: str):
    sql = """
        SELECT
            e.id,
            e.notes,
            e.exercise_catalog_id,
            e.exercise_name,
            e.weight_used,
            e.weight_unit,
            e.weight_used_kg,
            e.num_of_sets,
            e.avg_reps,
            e.max_reps,
            w.id AS workout_id,
            w.date AS workout_date,
            COALESCE(string_agg(DISTINCT m.name, ','), '') AS muscles,
            COALESCE(
                string_agg(
                    DISTINCT (m.name || '::' || COALESCE(m.color, '')),
                    '||'
                ),
                ''
            ) AS muscle_data
        FROM exercise e
        JOIN workout w ON w.id = e.workout_id
        LEFT JOIN exercise_muscle em ON em.exercise_id = e.id
        LEFT JOIN muscle m ON m.id = em.muscle_id AND m.user_id = w.user_id
        WHERE w.user_id = :user_id
          AND (
            COALESCE(e.notes, '') ILIKE :q
            OR COALESCE(e.exercise_name, '') ILIKE :q
            OR COALESCE(m.name, '') ILIKE :q
            OR COALESCE(e.weight_used::text, '') ILIKE :q
            OR COALESCE(e.num_of_sets::text, '') ILIKE :q
            OR COALESCE(e.avg_reps::text, '') ILIKE :q
            OR COALESCE(e.max_reps::text, '') ILIKE :q
            OR COALESCE(w.date::text, '') ILIKE :q
          )
        GROUP BY e.id, e.notes, e.exercise_catalog_id, e.exercise_name,
                 e.weight_used, e.weight_unit, e.weight_used_kg, e.num_of_sets,
                 e.avg_reps, e.max_reps, w.id, w.date
        ORDER BY w.date DESC, e.id DESC
    """
    result = conn.execute(
        text(sql),
        {"user_id": user_id, "q": f"%{query}%"},
    )
    return result.mappings().all()


def get_exercise_with_workout(conn, exercise_id: int):
    """
    Returns exercise plus owning workout + user_id, so we can enforce permissions.
    """
    sql = """
        SELECT
            e.id,
            e.notes,
            e.exercise_catalog_id,
            e.exercise_name,
            e.weight_used,
            e.weight_unit,
            e.weight_used_kg,
            e.num_of_sets,
            e.avg_reps,
            e.max_reps,
            e.workout_id,
            w.user_id,
            w.date AS workout_date
        FROM exercise e
        JOIN workout w ON w.id = e.workout_id
        WHERE e.id = :exercise_id
    """
    result = conn.execute(text(sql), {"exercise_id": exercise_id})
    return result.mappings().fetchone()



def delete_exercise(conn, exercise_id: int) -> None:
    # Delete all muscle links for this exercise (child table)
    conn.execute(
        text("DELETE FROM exercise_muscle WHERE exercise_id = :exercise_id"),
        {"exercise_id": exercise_id},
    )

    # Now delete the exercise itself (parent row)
    conn.execute(
        text("DELETE FROM exercise WHERE id = :exercise_id"),
        {"exercise_id": exercise_id},
    )

    conn.commit()


def create_exercise(
    conn,
    workout_id,
    notes,
    weight_used,
    weight_unit,
    weight_used_kg,
    num_of_sets,
    avg_reps=None,
    max_reps=None,
    muscle_id=None,
    exercise_catalog_id=None,
    exercise_name=None,
    sets=None,
):
    """
    Create an exercise row and optionally link it to a muscle
    via exercise_muscle.
    """
    cur = conn.execute(
        text(
        """
        INSERT INTO exercise (
            workout_id,
            notes,
            exercise_catalog_id,
            exercise_name,
            weight_used,
            weight_unit,
            weight_used_kg,
            num_of_sets,
            avg_reps,
            max_reps
        )
        VALUES (
            :workout_id,
            :notes,
            :exercise_catalog_id,
            :exercise_name,
            :weight_used,
            :weight_unit,
            :weight_used_kg,
            :num_of_sets,
            :avg_reps,
            :max_reps
        )
        RETURNING id
        """,
        ),
        {
            "workout_id": workout_id,
            "notes": notes,
            "exercise_catalog_id": exercise_catalog_id,
            "exercise_name": exercise_name,
            "weight_used": weight_used,
            "weight_unit": weight_unit,
            "weight_used_kg": weight_used_kg,
            "num_of_sets": num_of_sets,
            "avg_reps": avg_reps,
            "max_reps": max_reps,
        },
    )
    exercise_id = cur.scalar_one()

    if muscle_id is not None:
        conn.execute(
            text("INSERT INTO exercise_muscle (muscle_id, exercise_id) VALUES (:muscle_id, :exercise_id)"),
            {"muscle_id": muscle_id, "exercise_id": exercise_id},
        )

    _replace_sets(conn, exercise_id, sets)

    conn.commit()
    return exercise_id



def update_exercise(
    conn,
    exercise_id,
    notes,
    weight_used,
    weight_unit,
    weight_used_kg,
    num_of_sets,
    avg_reps=None,
    max_reps=None,
    muscle_id=None,
    workout_id=None,
    exercise_catalog_id=None,
    exercise_name=None,
    sets=None,
):
    """
    Update exercise fields, its (single) muscle mapping, and optionally
    move it to a different workout.
    """
    if workout_id is None:
        conn.execute(
            text(
            """
            UPDATE exercise
            SET notes = :notes,
                exercise_catalog_id = :exercise_catalog_id,
                exercise_name = :exercise_name,
                weight_used = :weight_used,
                weight_unit = :weight_unit,
                weight_used_kg = :weight_used_kg,
                num_of_sets = :num_of_sets,
                avg_reps = :avg_reps,
                max_reps = :max_reps
            WHERE id = :exercise_id
            """,
            ),
            {
                "notes": notes,
                "exercise_catalog_id": exercise_catalog_id,
                "exercise_name": exercise_name,
                "weight_used": weight_used,
                "weight_unit": weight_unit,
                "weight_used_kg": weight_used_kg,
                "num_of_sets": num_of_sets,
                "avg_reps": avg_reps,
                "max_reps": max_reps,
                "exercise_id": exercise_id,
            },
        )
    else:
        conn.execute(
            text(
            """
            UPDATE exercise
            SET notes = :notes,
                exercise_catalog_id = :exercise_catalog_id,
                exercise_name = :exercise_name,
                weight_used = :weight_used,
                weight_unit = :weight_unit,
                weight_used_kg = :weight_used_kg,
                num_of_sets = :num_of_sets,
                avg_reps = :avg_reps,
                max_reps = :max_reps,
                workout_id = :workout_id
            WHERE id = :exercise_id
            """,
            ),
            {
                "notes": notes,
                "exercise_catalog_id": exercise_catalog_id,
                "exercise_name": exercise_name,
                "weight_used": weight_used,
                "weight_unit": weight_unit,
                "weight_used_kg": weight_used_kg,
                "num_of_sets": num_of_sets,
                "avg_reps": avg_reps,
                "max_reps": max_reps,
                "workout_id": workout_id,
                "exercise_id": exercise_id,
            },
        )

    # reset muscle mapping
    conn.execute(
        text("DELETE FROM exercise_muscle WHERE exercise_id = :exercise_id"),
        {"exercise_id": exercise_id},
    )

    if muscle_id is not None:
        conn.execute(
            text("INSERT INTO exercise_muscle (muscle_id, exercise_id) VALUES (:muscle_id, :exercise_id)"),
            {"muscle_id": muscle_id, "exercise_id": exercise_id},
        )

    _replace_sets(conn, exercise_id, sets)

    conn.commit()



def get_exercise_with_muscle(conn, exercise_id):
    """
    Return one exercise row plus its muscle_id (if any).
    """
    result = conn.execute(
        text(
        """
        SELECT
            e.*,
            em.muscle_id
        FROM exercise e
        LEFT JOIN exercise_muscle em
          ON e.id = em.exercise_id
        WHERE e.id = :exercise_id
        """,
        ),
        {"exercise_id": exercise_id},
    )
    return result.mappings().fetchone()


def count_exercises_for_workout(conn, workout_id: int) -> int:
    sql = "SELECT COUNT(*) AS count FROM exercise WHERE workout_id = :workout_id"
    result = conn.execute(text(sql), {"workout_id": workout_id})
    row = result.mappings().fetchone()
    return row["count"] if row else 0
