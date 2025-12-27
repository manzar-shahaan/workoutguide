# app/db/repositories/access_codes.py

from sqlalchemy import text


def get_by_code(conn, code: str):
    sql = """
        SELECT
            id,
            name,
            code,
            created_at,
            used_by_user_id,
            used_at
        FROM access_code
        WHERE code = :code
    """
    result = conn.execute(text(sql), {"code": code})
    return result.mappings().fetchone()


def get_by_name(conn, name: str):
    sql = """
        SELECT
            id,
            name,
            code,
            created_at,
            used_by_user_id,
            used_at
        FROM access_code
        WHERE name = :name
    """
    result = conn.execute(text(sql), {"name": name})
    return result.mappings().fetchone()


def create_access_code(conn, name: str, code: str) -> int:
    sql = """
        INSERT INTO access_code (name, code)
        VALUES (:name, :code)
        RETURNING id
    """
    cur = conn.execute(text(sql), {"name": name, "code": code})
    conn.commit()
    return cur.scalar_one()


def mark_used(conn, code: str, user_id: int) -> bool:
    sql = """
        UPDATE access_code
        SET used_by_user_id = :user_id,
            used_at = CURRENT_TIMESTAMP
        WHERE code = :code
          AND used_by_user_id IS NULL
    """
    result = conn.execute(text(sql), {"code": code, "user_id": user_id})
    conn.commit()
    return result.rowcount == 1
