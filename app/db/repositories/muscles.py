# app/db/repositories/muscles.py

from sqlalchemy import text

DEFAULT_MUSCLES = ["back", "arms", "chest", "abs", "legs", "cardio"]


def _normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def ensure_default_muscles(conn, user_id: int) -> None:
    existing = conn.execute(
        text("SELECT 1 FROM muscle WHERE user_id = :user_id LIMIT 1"),
        {"user_id": user_id},
    ).fetchone()
    if existing:
        return

    for name in DEFAULT_MUSCLES:
        conn.execute(
            text(
                """
                INSERT INTO muscle (user_id, name, is_default, active)
                VALUES (:user_id, :name, TRUE, TRUE)
                """
            ),
            {"user_id": user_id, "name": name},
        )
    conn.commit()


def list_muscles(conn, user_id: int, *, active_only: bool = True):
    sql = """
        SELECT id, name, is_default, active
        FROM muscle
        WHERE user_id = :user_id
    """
    if active_only:
        sql += " AND active = TRUE"
    sql += " ORDER BY name"
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().all()


def get_muscle(conn, user_id: int, muscle_id: int):
    result = conn.execute(
        text(
            """
            SELECT id, name, is_default, active
            FROM muscle
            WHERE user_id = :user_id AND id = :id
            """
        ),
        {"user_id": user_id, "id": muscle_id},
    )
    return result.mappings().fetchone()


def add_muscle(conn, user_id: int, name: str) -> int:
    name_norm = _normalize_name(name)
    if not name_norm:
        raise ValueError("Muscle name is required.")

    existing = conn.execute(
        text(
            """
            SELECT id, active
            FROM muscle
            WHERE user_id = :user_id AND name = :name
            """
        ),
        {"user_id": user_id, "name": name_norm},
    ).mappings().fetchone()

    if existing:
        if not existing["active"]:
            conn.execute(
                text(
                    """
                    UPDATE muscle
                    SET active = TRUE, is_default = FALSE
                    WHERE id = :id
                    """
                ),
                {"id": existing["id"]},
            )
            conn.commit()
        return existing["id"]

    result = conn.execute(
        text(
            """
            INSERT INTO muscle (user_id, name, is_default, active)
            VALUES (:user_id, :name, FALSE, TRUE)
            RETURNING id
            """
        ),
        {"user_id": user_id, "name": name_norm},
    )
    conn.commit()
    return result.scalar_one()


def deactivate_muscle(conn, user_id: int, muscle_id: int) -> None:
    conn.execute(
        text(
            """
            UPDATE muscle
            SET active = FALSE
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": muscle_id, "user_id": user_id},
    )
    conn.commit()


def rename_muscle(conn, user_id: int, muscle_id: int, new_name: str) -> int | None:
    name_norm = _normalize_name(new_name)
    if not name_norm:
        raise ValueError("Muscle name is required.")

    current = conn.execute(
        text(
            """
            SELECT id, name
            FROM muscle
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": muscle_id, "user_id": user_id},
    ).mappings().fetchone()

    if current is None:
        return None

    if current["name"] == name_norm:
        return current["id"]

    # If the target name already exists, just activate it.
    existing = conn.execute(
        text(
            """
            SELECT id, active
            FROM muscle
            WHERE user_id = :user_id AND name = :name
            """
        ),
        {"user_id": user_id, "name": name_norm},
    ).mappings().fetchone()

    if existing:
        if not existing["active"]:
            conn.execute(
                text(
                    """
                    UPDATE muscle
                    SET active = TRUE, is_default = FALSE
                    WHERE id = :id
                    """
                ),
                {"id": existing["id"]},
            )
        new_id = existing["id"]
    else:
        result = conn.execute(
            text(
                """
                INSERT INTO muscle (user_id, name, is_default, active)
                VALUES (:user_id, :name, FALSE, TRUE)
                RETURNING id
                """
            ),
            {"user_id": user_id, "name": name_norm},
        )
        new_id = result.scalar_one()

    # Deactivate old muscle to preserve historical references.
    conn.execute(
        text(
            """
            UPDATE muscle
            SET active = FALSE
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": muscle_id, "user_id": user_id},
    )

    conn.commit()
    return new_id


def reset_to_default(conn, user_id: int) -> None:
    conn.execute(
        text("UPDATE muscle SET active = FALSE WHERE user_id = :user_id"),
        {"user_id": user_id},
    )
    for name in DEFAULT_MUSCLES:
        conn.execute(
            text(
                """
                INSERT INTO muscle (user_id, name, is_default, active)
                VALUES (:user_id, :name, TRUE, TRUE)
                ON CONFLICT (user_id, name)
                DO UPDATE SET is_default = TRUE, active = TRUE
                """
            ),
            {"user_id": user_id, "name": name},
        )
    conn.commit()
