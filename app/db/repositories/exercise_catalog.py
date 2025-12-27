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
