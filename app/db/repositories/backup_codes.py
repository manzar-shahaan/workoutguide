# app/db/repositories/backup_codes.py

import secrets


def replace_codes(conn, user_id: int, count: int = 10):
    """
    Delete any existing backup codes for this user, generate `count` new codes,
    insert them, and return the list of plaintext codes (for display/download).
    """
    conn.execute("DELETE FROM totp_backup_code WHERE user_id = ?", (user_id,))

    codes = []
    for _ in range(count):
        # e.g., "a3f1-b932" style code – easy to read + type
        code = f"{secrets.token_hex(2)}-{secrets.token_hex(2)}"
        codes.append(code)
        conn.execute(
            """
            INSERT INTO totp_backup_code (user_id, code, used)
            VALUES (?, ?, 0)
            """,
            (user_id, code),
        )

    conn.commit()
    return codes


def list_codes(conn, user_id: int):
    """
    Return all backup codes for display (including used flag).
    """
    sql = """
        SELECT id, code, used, created_at
        FROM totp_backup_code
        WHERE user_id = ?
        ORDER BY id
    """
    cur = conn.execute(sql, (user_id,))
    return cur.fetchall()


def consume_code(conn, user_id: int, code: str) -> bool:
    """
    Try to use a backup code; returns True if valid+unused and marks it used.
    """
    sql = """
        SELECT id, used
        FROM totp_backup_code
        WHERE user_id = ? AND code = ?
    """
    cur = conn.execute(sql, (user_id, code))
    row = cur.fetchone()

    if row is None or row["used"]:
        return False

    conn.execute(
        "UPDATE totp_backup_code SET used = 1 WHERE id = ?",
        (row["id"],),
    )
    conn.commit()
    return True
