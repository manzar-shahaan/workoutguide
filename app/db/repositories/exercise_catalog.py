# app/db/repositories/exercise_catalog.py

from sqlalchemy import text


def _normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def list_for_muscle(conn, user_id: int, muscle_id: int):
    sql = """
        SELECT id, name
        FROM exercise_catalog
        WHERE user_id = :user_id AND muscle_id = :muscle_id
        ORDER BY name
    """
    result = conn.execute(text(sql), {"user_id": user_id, "muscle_id": muscle_id})
    return result.mappings().all()


def list_for_muscle_with_counts(conn, user_id: int, muscle_id: int):
    sql = """
        SELECT
            ec.id,
            ec.name,
            m.name AS muscle_name,
            m.color AS muscle_color,
            COUNT(e.id) AS exercise_count,
            last.weight_used AS last_weight_used,
            last.weight_unit AS last_weight_unit,
            last.num_of_sets AS last_num_of_sets,
            last.workout_date AS last_workout_date
        FROM exercise_catalog ec
        JOIN muscle m ON m.id = ec.muscle_id AND m.user_id = ec.user_id
        LEFT JOIN exercise e ON e.exercise_catalog_id = ec.id
        LEFT JOIN LATERAL (
            SELECT e2.weight_used, e2.weight_unit, e2.num_of_sets, w2.date AS workout_date
            FROM exercise e2
            JOIN workout w2 ON w2.id = e2.workout_id
            WHERE e2.exercise_catalog_id = ec.id
            ORDER BY w2.date DESC NULLS LAST, e2.created_at DESC
            LIMIT 1
        ) AS last ON TRUE
        WHERE ec.user_id = :user_id
          AND ec.muscle_id = :muscle_id
        GROUP BY ec.id, ec.name, m.name, m.color,
                 last.weight_used, last.weight_unit, last.num_of_sets, last.workout_date
        ORDER BY ec.name
    """
    result = conn.execute(
        text(sql),
        {"user_id": user_id, "muscle_id": muscle_id},
    )
    return result.mappings().all()


def list_all_with_counts_and_last(conn, user_id: int):
    sql = """
        SELECT
            ec.id,
            ec.name,
            ec.muscle_id,
            m.name AS muscle_name,
            m.color AS muscle_color,
            COUNT(e.id) AS exercise_count,
            last.weight_used AS last_weight_used,
            last.weight_unit AS last_weight_unit,
            last.num_of_sets AS last_num_of_sets,
            last.workout_date AS last_workout_date,
            ml.muscle_last_logged
        FROM exercise_catalog ec
        JOIN muscle m ON m.id = ec.muscle_id AND m.user_id = ec.user_id
        LEFT JOIN exercise e ON e.exercise_catalog_id = ec.id
        LEFT JOIN LATERAL (
            SELECT e2.weight_used, e2.weight_unit, e2.num_of_sets, w2.date AS workout_date
            FROM exercise e2
            JOIN workout w2 ON w2.id = e2.workout_id
            WHERE e2.exercise_catalog_id = ec.id
            ORDER BY w2.date DESC NULLS LAST, e2.created_at DESC
            LIMIT 1
        ) AS last ON TRUE
        LEFT JOIN (
            SELECT ec2.muscle_id, MAX(w2.date) AS muscle_last_logged
            FROM exercise_catalog ec2
            JOIN exercise e2 ON e2.exercise_catalog_id = ec2.id
            JOIN workout w2 ON w2.id = e2.workout_id
            WHERE ec2.user_id = :user_id
            GROUP BY ec2.muscle_id
        ) AS ml ON ml.muscle_id = ec.muscle_id
        WHERE ec.user_id = :user_id
        GROUP BY ec.id, ec.name, ec.muscle_id, m.name, m.color,
                 last.weight_used, last.weight_unit, last.num_of_sets, last.workout_date,
                 ml.muscle_last_logged
        ORDER BY ml.muscle_last_logged ASC NULLS FIRST, m.name, ec.name
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().all()

def list_all_with_counts(conn, user_id: int):
    sql = """
        SELECT ec.id, ec.name, ec.muscle_id, COUNT(e.id) AS exercise_count
        FROM exercise_catalog ec
        LEFT JOIN exercise e ON e.exercise_catalog_id = ec.id
        WHERE ec.user_id = :user_id
        GROUP BY ec.id, ec.name, ec.muscle_id
        ORDER BY ec.name
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().all()


def get_template(conn, user_id: int, template_id: int):
    sql = """
        SELECT id, name, muscle_id
        FROM exercise_catalog
        WHERE user_id = :user_id AND id = :id
    """
    result = conn.execute(text(sql), {"user_id": user_id, "id": template_id})
    return result.mappings().fetchone()


def search_for_muscle(conn, user_id: int, muscle_id: int, query: str):
    sql = """
        SELECT id, name
        FROM exercise_catalog
        WHERE user_id = :user_id
          AND muscle_id = :muscle_id
          AND name ILIKE :q
        ORDER BY name
        LIMIT 25
    """
    result = conn.execute(
        text(sql),
        {"user_id": user_id, "muscle_id": muscle_id, "q": f"%{query}%"},
    )
    return result.mappings().all()


def search_for_muscle_with_counts(conn, user_id: int, muscle_id: int, query: str):
    sql = """
        SELECT
            ec.id,
            ec.name,
            COUNT(e.id) AS exercise_count,
            m.name AS muscle_name,
            m.color AS muscle_color,
            last.weight_used AS last_weight_used,
            last.weight_unit AS last_weight_unit,
            last.num_of_sets AS last_num_of_sets,
            last.workout_date AS last_workout_date
        FROM exercise_catalog ec
        JOIN muscle m ON m.id = ec.muscle_id AND m.user_id = ec.user_id
        LEFT JOIN exercise e ON e.exercise_catalog_id = ec.id
        LEFT JOIN LATERAL (
            SELECT e2.weight_used, e2.weight_unit, e2.num_of_sets, w2.date AS workout_date
            FROM exercise e2
            JOIN workout w2 ON w2.id = e2.workout_id
            WHERE e2.exercise_catalog_id = ec.id
            ORDER BY w2.date DESC NULLS LAST, e2.created_at DESC
            LIMIT 1
        ) AS last ON TRUE
        WHERE ec.user_id = :user_id
          AND ec.muscle_id = :muscle_id
          AND ec.name ILIKE :q
        GROUP BY ec.id, ec.name, m.name, m.color,
                 last.weight_used, last.weight_unit, last.num_of_sets, last.workout_date
        ORDER BY ec.name
        LIMIT 25
    """
    result = conn.execute(
        text(sql),
        {"user_id": user_id, "muscle_id": muscle_id, "q": f"%{query}%"},
    )
    return result.mappings().all()


def count_for_user(conn, user_id: int) -> int:
    sql = """
        SELECT COUNT(*) AS count
        FROM exercise_catalog
        WHERE user_id = :user_id
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    row = result.mappings().fetchone()
    return row["count"] if row else 0


def search_all_with_counts(conn, user_id: int, query: str):
    sql = """
        SELECT
            ec.id,
            ec.name,
            ec.muscle_id,
            m.name AS muscle_name,
            m.color AS muscle_color,
            COUNT(e.id) AS exercise_count,
            last.weight_used AS last_weight_used,
            last.weight_unit AS last_weight_unit,
            last.num_of_sets AS last_num_of_sets,
            last.workout_date AS last_workout_date
        FROM exercise_catalog ec
        JOIN muscle m ON m.id = ec.muscle_id AND m.user_id = ec.user_id
        LEFT JOIN exercise e ON e.exercise_catalog_id = ec.id
        LEFT JOIN LATERAL (
            SELECT e2.weight_used, e2.weight_unit, e2.num_of_sets, w2.date AS workout_date
            FROM exercise e2
            JOIN workout w2 ON w2.id = e2.workout_id
            WHERE e2.exercise_catalog_id = ec.id
            ORDER BY w2.date DESC NULLS LAST, e2.created_at DESC
            LIMIT 1
        ) AS last ON TRUE
        WHERE ec.user_id = :user_id
          AND ec.name ILIKE :q
        GROUP BY ec.id, ec.name, ec.muscle_id, m.name, m.color,
                 last.weight_used, last.weight_unit, last.num_of_sets, last.workout_date
        ORDER BY ec.name
        LIMIT 25
    """
    result = conn.execute(
        text(sql),
        {"user_id": user_id, "q": f"%{query}%"},
    )
    return result.mappings().all()


def count_for_muscle(conn, user_id: int, muscle_id: int) -> int:
    sql = """
        SELECT COUNT(*) AS count
        FROM exercise_catalog
        WHERE user_id = :user_id AND muscle_id = :muscle_id
    """
    result = conn.execute(text(sql), {"user_id": user_id, "muscle_id": muscle_id})
    row = result.mappings().fetchone()
    return row["count"] if row else 0


def get_by_name(conn, user_id: int, muscle_id: int, name: str):
    name_norm = _normalize_name(name)
    if not name_norm:
        return None
    sql = """
        SELECT id, name
        FROM exercise_catalog
        WHERE user_id = :user_id AND muscle_id = :muscle_id AND name = :name
    """
    result = conn.execute(
        text(sql),
        {"user_id": user_id, "muscle_id": muscle_id, "name": name_norm},
    )
    return result.mappings().fetchone()


def rename_template(
    conn,
    user_id: int,
    muscle_id: int,
    template_id: int,
    new_name: str,
) -> int | None:
    name_norm = _normalize_name(new_name)
    if not name_norm:
        raise ValueError("Template name is required.")

    current = get_template(conn, user_id, template_id)
    if current is None or current["muscle_id"] != muscle_id:
        return None

    if current["name"] == name_norm:
        return current["id"]

    existing = get_by_name(conn, user_id, muscle_id, name_norm)
    if existing:
        raise ValueError(
            "An exercise template with that name already exists. Use merge instead."
        )

    conn.execute(
        text(
            """
            UPDATE exercise_catalog
            SET name = :name
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": template_id, "user_id": user_id, "name": name_norm},
    )
    conn.execute(
        text(
            """
            UPDATE exercise
            SET exercise_name = :name
            WHERE exercise_catalog_id = :id
            """
        ),
        {"id": template_id, "name": name_norm},
    )
    conn.commit()
    return template_id


def merge_templates(
    conn,
    user_id: int,
    muscle_id: int,
    source_template_id: int,
    target_template_id: int,
    *,
    commit: bool = True,
) -> None:
    if source_template_id == target_template_id:
        raise ValueError("Pick two different templates to merge.")

    source = get_template(conn, user_id, source_template_id)
    target = get_template(conn, user_id, target_template_id)
    if source is None or target is None:
        raise ValueError("Template not found.")
    if (
        source["muscle_id"] != muscle_id
        or target["muscle_id"] != muscle_id
        or source["muscle_id"] != target["muscle_id"]
    ):
        raise ValueError("Templates must belong to the same muscle.")

    target_name = target["name"]

    conn.execute(
        text(
            """
            UPDATE exercise
            SET exercise_catalog_id = :target_id,
                exercise_name = :target_name
            WHERE exercise_catalog_id = :source_id
            """
        ),
        {
            "target_id": target_template_id,
            "target_name": target_name,
            "source_id": source_template_id,
        },
    )
    conn.execute(
        text(
            """
            UPDATE exercise
            SET exercise_name = :target_name
            WHERE exercise_catalog_id = :target_id
            """
        ),
        {"target_id": target_template_id, "target_name": target_name},
    )
    conn.execute(
        text(
            """
            DELETE FROM exercise_catalog
            WHERE id = :source_id AND user_id = :user_id
            """
        ),
        {"source_id": source_template_id, "user_id": user_id},
    )
    if commit:
        conn.commit()


def get_or_create(
    conn,
    user_id: int,
    muscle_id: int,
    name: str,
    *,
    commit: bool = True,
) -> int | None:
    name_norm = _normalize_name(name)
    if not name_norm:
        return None
    existing = get_by_name(conn, user_id, muscle_id, name_norm)
    if existing:
        return existing["id"]
    result = conn.execute(
        text(
            """
            INSERT INTO exercise_catalog (user_id, muscle_id, name)
            VALUES (:user_id, :muscle_id, :name)
            RETURNING id
            """
        ),
        {"user_id": user_id, "muscle_id": muscle_id, "name": name_norm},
    )
    if commit:
        conn.commit()
    return result.scalar_one()


def ensure_names_for_muscle(conn, user_id: int, muscle_id: int, names: list[str]) -> dict[str, int]:
    ids: dict[str, int] = {}
    for name in names:
        name_norm = _normalize_name(name)
        if not name_norm:
            continue
        existing = get_by_name(conn, user_id, muscle_id, name_norm)
        if existing:
            ids[name_norm] = existing["id"]
            continue
        result = conn.execute(
            text(
                """
                INSERT INTO exercise_catalog (user_id, muscle_id, name)
                VALUES (:user_id, :muscle_id, :name)
                RETURNING id
                """
            ),
            {"user_id": user_id, "muscle_id": muscle_id, "name": name_norm},
        )
        ids[name_norm] = result.scalar_one()
    conn.commit()
    return ids
