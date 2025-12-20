# app/db/repositories/exercises.py

def list_for_workout(conn, workout_id: int):
    sql = """
        SELECT
            e.id,
            e.notes,
            e.weight_used,
            e.num_of_sets,
            COALESCE(GROUP_CONCAT(DISTINCT m.name), '') AS muscles
        FROM exercise e
        LEFT JOIN exercise_muscle em ON em.exercise_id = e.id
        LEFT JOIN muscle m ON m.id = em.muscle_id
        WHERE e.workout_id = ?
        GROUP BY e.id, e.notes, e.weight_used, e.num_of_sets
        ORDER BY e.id
    """
    cur = conn.execute(sql, (workout_id,))
    return cur.fetchall()


def get_exercise_with_workout(conn, exercise_id: int):
    """
    Returns exercise plus owning workout + user_id, so we can enforce permissions.
    """
    sql = """
        SELECT
            e.id,
            e.notes,
            e.weight_used,
            e.num_of_sets,
            e.workout_id,
            w.user_id,
            w.date AS workout_date
        FROM exercise e
        JOIN workout w ON w.id = e.workout_id
        WHERE e.id = ?
    """
    cur = conn.execute(sql, (exercise_id,))
    return cur.fetchone()



# app/db/repositories/exercises.py
import sqlite3

def delete_exercise(conn, exercise_id: int) -> None:
    # Delete all muscle links for this exercise (child table)
    conn.execute(
        "DELETE FROM exercise_muscle WHERE exercise_id = ?",
        (exercise_id,),
    )

    # Now delete the exercise itself (parent row)
    conn.execute(
        "DELETE FROM exercise WHERE id = ?",
        (exercise_id,),
    )

    conn.commit()


def create_exercise(conn, workout_id, notes, weight_used, num_of_sets, muscle_id=None):
    """
    Create an exercise row and optionally link it to a muscle
    via exercise_muscle.
    """
    cur = conn.execute(
        """
        INSERT INTO exercise (workout_id, notes, weight_used, num_of_sets)
        VALUES (?, ?, ?, ?)
        """,
        (workout_id, notes, weight_used, num_of_sets),
    )
    exercise_id = cur.lastrowid

    if muscle_id is not None:
        conn.execute(
            "INSERT INTO exercise_muscle (muscle_id, exercise_id) VALUES (?, ?)",
            (muscle_id, exercise_id),
        )

    conn.commit()
    return exercise_id



def update_exercise(
    conn,
    exercise_id,
    notes,
    weight_used,
    num_of_sets,
    muscle_id=None,
    workout_id=None,
):
    """
    Update exercise fields, its (single) muscle mapping, and optionally
    move it to a different workout.
    """
    if workout_id is None:
        conn.execute(
            """
            UPDATE exercise
            SET notes = ?, weight_used = ?, num_of_sets = ?
            WHERE id = ?
            """,
            (notes, weight_used, num_of_sets, exercise_id),
        )
    else:
        conn.execute(
            """
            UPDATE exercise
            SET notes = ?, weight_used = ?, num_of_sets = ?, workout_id = ?
            WHERE id = ?
            """,
            (notes, weight_used, num_of_sets, workout_id, exercise_id),
        )

    # reset muscle mapping
    conn.execute(
        "DELETE FROM exercise_muscle WHERE exercise_id = ?",
        (exercise_id,),
    )

    if muscle_id is not None:
        conn.execute(
            "INSERT INTO exercise_muscle (muscle_id, exercise_id) VALUES (?, ?)",
            (muscle_id, exercise_id),
        )

    conn.commit()



def get_exercise_with_muscle(conn, exercise_id):
    """
    Return one exercise row plus its muscle_id (if any).
    """
    cur = conn.execute(
        """
        SELECT
            e.*,
            em.muscle_id
        FROM exercise e
        LEFT JOIN exercise_muscle em
          ON e.id = em.exercise_id
        WHERE e.id = ?
        """,
        (exercise_id,),
    )
    return cur.fetchone()


def count_exercises_for_workout(conn, workout_id: int) -> int:
    sql = "SELECT COUNT(*) AS count FROM exercise WHERE workout_id = ?"
    cur = conn.execute(sql, (workout_id,))
    row = cur.fetchone()
    return row["count"] if row else 0
