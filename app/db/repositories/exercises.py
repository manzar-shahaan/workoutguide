# app/db/repositories/exercises.py

from sqlalchemy import text


def get_sets_for_exercise(conn, exercise_id: int):
    sql = """
        SELECT set_index, weight_used, weight_unit, weight_used_kg, reps,
               duration_seconds, distance, distance_unit
        FROM exercise_set
        WHERE exercise_id = :exercise_id
        ORDER BY set_index
    """
    result = conn.execute(text(sql), {"exercise_id": exercise_id})
    return result.mappings().all()


def _replace_sets(conn, exercise_id: int, sets: list[dict] | None) -> None:
    """
    sets: [{"weight_used": float|None, "weight_unit": str|None,
             "weight_used_kg": float|None, "reps": int|None,
             "duration_seconds": int|None, "distance": float|None,
             "distance_unit": str|None}, ...]
    A given exercise only ever populates the weight/reps trio (strength/
    mobility/plyometrics) or the duration/distance trio (cardio) -- the
    other stays NULL. Full replace -- simpler and safer than diffing for a
    handful of rows per exercise, and this always runs inside the caller's
    transaction.
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
                    (exercise_id, set_index, weight_used, weight_unit, weight_used_kg, reps,
                     duration_seconds, distance, distance_unit)
                VALUES (:exercise_id, :set_index, :weight_used, :weight_unit, :weight_used_kg, :reps,
                        :duration_seconds, :distance, :distance_unit)
                """
            ),
            {
                "exercise_id": exercise_id,
                "set_index": index,
                "weight_used": set_row.get("weight_used"),
                "weight_unit": set_row.get("weight_unit"),
                "weight_used_kg": set_row.get("weight_used_kg"),
                "reps": set_row.get("reps"),
                "duration_seconds": set_row.get("duration_seconds"),
                "distance": set_row.get("distance"),
                "distance_unit": set_row.get("distance_unit"),
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
            e.total_duration_seconds,
            e.total_distance,
            e.distance_unit,
            COALESCE(ec.metric_type, 'resistance') AS metric_type,
            (SELECT string_agg(tg.name, '||' ORDER BY tg.sort_order)
             FROM exercise_catalog_tag ect JOIN tag tg ON tg.slug = ect.tag_slug
             WHERE ect.exercise_catalog_id = e.exercise_catalog_id) AS tag_data,
            COALESCE(string_agg(br.name, ',' ORDER BY ecr.rank), '') AS muscles,
            COALESCE(string_agg(br.name, '||' ORDER BY ecr.rank), '') AS muscle_data
        FROM exercise e
        JOIN workout w ON w.id = e.workout_id
        LEFT JOIN exercise_catalog ec ON ec.id = e.exercise_catalog_id
        LEFT JOIN exercise_catalog_region ecr ON ecr.exercise_catalog_id = e.exercise_catalog_id
        LEFT JOIN body_region br ON br.slug = ecr.region_slug
        WHERE e.workout_id = :workout_id
        GROUP BY e.id, e.notes, e.exercise_catalog_id, e.exercise_name,
                 e.weight_used, e.weight_unit, e.weight_used_kg, e.num_of_sets,
                 e.avg_reps, e.max_reps, e.total_duration_seconds, e.total_distance,
                 e.distance_unit, ec.metric_type
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
            e.total_duration_seconds,
            e.total_distance,
            e.distance_unit,
            COALESCE(ec.metric_type, 'resistance') AS metric_type,
            (SELECT string_agg(tg.name, '||' ORDER BY tg.sort_order)
             FROM exercise_catalog_tag ect JOIN tag tg ON tg.slug = ect.tag_slug
             WHERE ect.exercise_catalog_id = e.exercise_catalog_id) AS tag_data,
            w.id AS workout_id,
            w.date AS workout_date,
            COALESCE(string_agg(DISTINCT br.name, ',' ORDER BY br.name), '') AS muscles,
            COALESCE(string_agg(DISTINCT br.name, '||' ORDER BY br.name), '') AS muscle_data
        FROM exercise e
        JOIN workout w ON w.id = e.workout_id
        LEFT JOIN exercise_catalog ec ON ec.id = e.exercise_catalog_id
        LEFT JOIN exercise_catalog_region ecr ON ecr.exercise_catalog_id = e.exercise_catalog_id
        LEFT JOIN body_region br ON br.slug = ecr.region_slug
        WHERE w.user_id = :user_id
          AND (
            COALESCE(e.notes, '') ILIKE :q
            OR COALESCE(e.exercise_name, '') ILIKE :q
            OR COALESCE(br.name, '') ILIKE :q
            OR COALESCE(e.weight_used::text, '') ILIKE :q
            OR COALESCE(e.num_of_sets::text, '') ILIKE :q
            OR COALESCE(e.avg_reps::text, '') ILIKE :q
            OR COALESCE(e.max_reps::text, '') ILIKE :q
            OR COALESCE(w.date::text, '') ILIKE :q
          )
        GROUP BY e.id, e.notes, e.exercise_catalog_id, e.exercise_name,
                 e.weight_used, e.weight_unit, e.weight_used_kg, e.num_of_sets,
                 e.avg_reps, e.max_reps, e.total_duration_seconds, e.total_distance,
                 e.distance_unit, ec.metric_type, w.id, w.date
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
            e.total_duration_seconds,
            e.total_distance,
            e.distance_unit,
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
    total_duration_seconds=None,
    total_distance=None,
    distance_unit=None,
    exercise_catalog_id=None,
    exercise_name=None,
    sets=None,
):
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
            max_reps,
            total_duration_seconds,
            total_distance,
            distance_unit
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
            :max_reps,
            :total_duration_seconds,
            :total_distance,
            :distance_unit
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
            "total_duration_seconds": total_duration_seconds,
            "total_distance": total_distance,
            "distance_unit": distance_unit,
        },
    )
    exercise_id = cur.scalar_one()

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
    total_duration_seconds=None,
    total_distance=None,
    distance_unit=None,
    workout_id=None,
    exercise_catalog_id=None,
    exercise_name=None,
    sets=None,
):
    """
    Update exercise fields and optionally move it to a different workout.
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
                max_reps = :max_reps,
                total_duration_seconds = :total_duration_seconds,
                total_distance = :total_distance,
                distance_unit = :distance_unit
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
                "total_duration_seconds": total_duration_seconds,
                "total_distance": total_distance,
                "distance_unit": distance_unit,
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
                total_duration_seconds = :total_duration_seconds,
                total_distance = :total_distance,
                distance_unit = :distance_unit,
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
                "total_duration_seconds": total_duration_seconds,
                "total_distance": total_distance,
                "distance_unit": distance_unit,
                "workout_id": workout_id,
                "exercise_id": exercise_id,
            },
        )

    _replace_sets(conn, exercise_id, sets)

    conn.commit()



def count_exercises_for_workout(conn, workout_id: int) -> int:
    sql = "SELECT COUNT(*) AS count FROM exercise WHERE workout_id = :workout_id"
    result = conn.execute(text(sql), {"workout_id": workout_id})
    row = result.mappings().fetchone()
    return row["count"] if row else 0
