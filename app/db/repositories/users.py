# app/db/repositories/users.py

def create_user(
    conn,
    name: str,
    email: str,
    password_hash: str,
    weight_unit: str = "lb",
    recovery_email: str | None = None,
):
    """
    Create a new user row.

    weight_unit and recovery_email are optional and have sensible defaults.
    """
    sql = """
        INSERT INTO user (name, email, password_hash, weight_unit, recovery_email)
        VALUES (?, ?, ?, ?, ?)
    """
    cur = conn.execute(sql, (name, email, password_hash, weight_unit, recovery_email))
    conn.commit()
    return cur.lastrowid


def get_user_by_email(conn, email: str):
    sql = """
        SELECT
            id,
            name,
            email,
            password_hash,
            weight_unit,
            recovery_email,
            totp_secret,
            totp_enabled,
            last_login,
            created_at
        FROM user
        WHERE email = ?
    """
    cur = conn.execute(sql, (email,))
    return cur.fetchone()


def get_user(conn, user_id: int):
    sql = """
        SELECT
            id,
            name,
            email,
            password_hash,
            weight_unit,
            recovery_email,
            totp_secret,
            totp_enabled,
            last_login,
            created_at
        FROM user
        WHERE id = ?
    """
    cur = conn.execute(sql, (user_id,))
    return cur.fetchone()


def update_profile(
    conn,
    user_id: int,
    *,
    name: str,
    email: str,
    recovery_email: str | None,
):
    """
    Update basic profile fields (name, primary email, recovery email).
    """
    sql = """
        UPDATE user
        SET name = ?, email = ?, recovery_email = ?
        WHERE id = ?
    """
    conn.execute(sql, (name, email, recovery_email, user_id))
    conn.commit()


def update_password(conn, user_id: int, new_password_hash: str):
    """
    Update the user's password hash.
    """
    sql = """
        UPDATE user
        SET password_hash = ?
        WHERE id = ?
    """
    conn.execute(sql, (new_password_hash, user_id))
    conn.commit()


def update_weight_unit(conn, user_id: int, weight_unit: str):
    """
    Update the user's preferred weight unit ('lb' or 'kg').
    """
    sql = """
        UPDATE user
        SET weight_unit = ?
        WHERE id = ?
    """
    conn.execute(sql, (weight_unit, user_id))
    conn.commit()


def enable_totp(conn, user_id: int, secret: str):
    """
    Set the TOTP secret and mark 2FA as enabled.
    """
    sql = """
        UPDATE user
        SET totp_secret = ?, totp_enabled = 1
        WHERE id = ?
    """
    conn.execute(sql, (secret, user_id))
    conn.commit()
