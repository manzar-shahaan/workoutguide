# app/db/repositories/muscles.py

import re

from sqlalchemy import text

from . import exercise_catalog as exercise_catalog_repo

DEFAULT_MUSCLES = ["back", "arms", "chest", "abs", "legs", "cardio"]
DEFAULT_MUSCLE_COLORS = {
    "back": "#38bdf8",
    "arms": "#f97316",
    "chest": "#ef4444",
    "abs": "#eab308",
    "legs": "#22c55e",
    "cardio": "#14b8a6",
}
DEFAULT_CUSTOM_COLOR = "#64748b"
COLOR_REGEX = re.compile(r"^#[0-9a-fA-F]{6}$")


def _normalize_name(name: str) -> str:
    return (name or "").strip().lower()


def _normalize_color(color: str | None) -> str | None:
    if not color:
        return None
    color = color.strip().lower()
    if not COLOR_REGEX.match(color):
        return None
    return color


def _default_color_for(name: str) -> str:
    return DEFAULT_MUSCLE_COLORS.get(name, DEFAULT_CUSTOM_COLOR)


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
                INSERT INTO muscle (user_id, name, color, is_default, active)
                VALUES (:user_id, :name, :color, TRUE, TRUE)
                """
            ),
            {"user_id": user_id, "name": name, "color": _default_color_for(name)},
        )
    conn.commit()


def list_muscles(conn, user_id: int, *, active_only: bool = True):
    sql = """
        SELECT id, name, color, is_default, active
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
            SELECT id, name, color, is_default, active
            FROM muscle
            WHERE user_id = :user_id AND id = :id
            """
        ),
        {"user_id": user_id, "id": muscle_id},
    )
    return result.mappings().fetchone()


def add_muscle(conn, user_id: int, name: str, color: str | None = None) -> int:
    name_norm = _normalize_name(name)
    if not name_norm:
        raise ValueError("Muscle name is required.")

    color_norm = _normalize_color(color) or _default_color_for(name_norm)

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
                    SET active = TRUE,
                        is_default = FALSE,
                        color = :color
                    WHERE id = :id
                    """
                ),
                {"id": existing["id"], "color": color_norm},
            )
            conn.commit()
        else:
            conn.execute(
                text(
                    """
                    UPDATE muscle
                    SET color = :color
                    WHERE id = :id
                    """
                ),
                {"id": existing["id"], "color": color_norm},
            )
            conn.commit()
        return existing["id"]

    result = conn.execute(
        text(
            """
            INSERT INTO muscle (user_id, name, color, is_default, active)
            VALUES (:user_id, :name, :color, FALSE, TRUE)
            RETURNING id
            """
        ),
        {"user_id": user_id, "name": name_norm, "color": color_norm},
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


def rename_muscle(
    conn,
    user_id: int,
    muscle_id: int,
    new_name: str,
    color: str | None = None,
) -> int | None:
    name_norm = _normalize_name(new_name)
    if not name_norm:
        raise ValueError("Muscle name is required.")

    current = conn.execute(
        text(
            """
            SELECT id, name, color
            FROM muscle
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": muscle_id, "user_id": user_id},
    ).mappings().fetchone()

    if current is None:
        return None

    color_norm = _normalize_color(color) or current["color"] or _default_color_for(name_norm)

    if current["name"] == name_norm:
        conn.execute(
            text(
                """
                UPDATE muscle
                SET color = :color
                WHERE id = :id AND user_id = :user_id
                """
            ),
            {"id": muscle_id, "user_id": user_id, "color": color_norm},
        )
        conn.commit()
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
                    SET active = TRUE,
                        is_default = FALSE,
                        color = :color
                    WHERE id = :id
                    """
                ),
                {"id": existing["id"], "color": color_norm},
            )
        else:
            conn.execute(
                text(
                    """
                    UPDATE muscle
                    SET color = :color
                    WHERE id = :id
                    """
                ),
                {"id": existing["id"], "color": color_norm},
            )
        new_id = existing["id"]
    else:
        result = conn.execute(
            text(
                """
                INSERT INTO muscle (user_id, name, color, is_default, active)
                VALUES (:user_id, :name, :color, FALSE, TRUE)
                RETURNING id
                """
            ),
            {"user_id": user_id, "name": name_norm, "color": color_norm},
        )
        new_id = result.scalar_one()

    # Deactivate old muscle to preserve historical references.
    conn.execute(
        text(
            """
            UPDATE muscle
            SET active = FALSE,
                color = :color
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": muscle_id, "user_id": user_id, "color": color_norm},
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
                INSERT INTO muscle (user_id, name, color, is_default, active)
                VALUES (:user_id, :name, :color, TRUE, TRUE)
                ON CONFLICT (user_id, name)
                DO UPDATE SET is_default = TRUE,
                              active = TRUE,
                              color = :color
                """
            ),
            {"user_id": user_id, "name": name, "color": _default_color_for(name)},
        )
    conn.commit()


def merge_muscles(
    conn,
    user_id: int,
    source_muscle_id: int,
    target_muscle_id: int,
) -> None:
    if source_muscle_id == target_muscle_id:
        raise ValueError("Pick two different muscles to merge.")

    source = get_muscle(conn, user_id, source_muscle_id)
    target = get_muscle(conn, user_id, target_muscle_id)
    if source is None or target is None:
        raise ValueError("Muscle not found.")

    source_catalogs = conn.execute(
        text(
            """
            SELECT id, name
            FROM exercise_catalog
            WHERE user_id = :user_id AND muscle_id = :muscle_id
            """
        ),
        {"user_id": user_id, "muscle_id": source_muscle_id},
    ).mappings().all()

    for row in source_catalogs:
        existing = exercise_catalog_repo.get_by_name(
            conn,
            user_id,
            target_muscle_id,
            row["name"],
        )
        if existing:
            exercise_catalog_repo.merge_templates(
                conn,
                user_id,
                target_muscle_id,
                row["id"],
                existing["id"],
                commit=False,
            )
        else:
            conn.execute(
                text(
                    """
                    UPDATE exercise_catalog
                    SET muscle_id = :target_id
                    WHERE id = :catalog_id AND user_id = :user_id
                    """
                ),
                {
                    "target_id": target_muscle_id,
                    "catalog_id": row["id"],
                    "user_id": user_id,
                },
            )

    conn.execute(
        text(
            """
            DELETE FROM exercise_muscle
            WHERE muscle_id = :source_id
              AND exercise_id IN (
                SELECT exercise_id FROM exercise_muscle WHERE muscle_id = :target_id
              )
            """
        ),
        {"source_id": source_muscle_id, "target_id": target_muscle_id},
    )
    conn.execute(
        text(
            """
            UPDATE exercise_muscle
            SET muscle_id = :target_id
            WHERE muscle_id = :source_id
            """
        ),
        {"source_id": source_muscle_id, "target_id": target_muscle_id},
    )
    conn.execute(
        text(
            """
            UPDATE muscle
            SET active = FALSE
            WHERE id = :id AND user_id = :user_id
            """
        ),
        {"id": source_muscle_id, "user_id": user_id},
    )
    conn.commit()
