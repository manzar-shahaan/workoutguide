# app/db/repositories/users.py

from sqlalchemy import text

def create_user(
    conn,
    name: str,
    email: str,
    password_hash: str,
    weight_unit: str = "lb",
    week_start: str = "sun",
    recovery_email: str | None = None,
    *,
    commit: bool = True,
):
    """
    Create a new user row.

    weight_unit and recovery_email are optional and have sensible defaults.
    """
    sql = """
        INSERT INTO app_user (name, email, password_hash, weight_unit, week_start, recovery_email)
        VALUES (:name, :email, :password_hash, :weight_unit, :week_start, :recovery_email)
        RETURNING id
    """
    cur = conn.execute(
        text(sql),
        {
            "name": name,
            "email": email,
            "password_hash": password_hash,
            "weight_unit": weight_unit,
            "week_start": week_start,
            "recovery_email": recovery_email,
        },
    )
    if commit:
        conn.commit()
    return cur.scalar_one()


def delete_user(conn, user_id: int):
    sql = "DELETE FROM app_user WHERE id = :user_id"
    conn.execute(text(sql), {"user_id": user_id})
    conn.commit()


def get_user_by_email(conn, email: str):
    sql = """
        SELECT
            id,
            name,
            email,
            password_hash,
            weight_unit,
            week_start,
            recovery_email,
            totp_secret,
            totp_enabled,
            last_login,
            created_at
        FROM app_user
        WHERE email = :email
    """
    result = conn.execute(text(sql), {"email": email})
    return result.mappings().fetchone()


def get_user(conn, user_id: int):
    sql = """
        SELECT
            id,
            name,
            email,
            password_hash,
            weight_unit,
            week_start,
            recovery_email,
            totp_secret,
            totp_enabled,
            last_login,
            created_at
        FROM app_user
        WHERE id = :user_id
    """
    result = conn.execute(text(sql), {"user_id": user_id})
    return result.mappings().fetchone()


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
        UPDATE app_user
        SET name = :name, email = :email, recovery_email = :recovery_email
        WHERE id = :user_id
    """
    conn.execute(
        text(sql),
        {
            "name": name,
            "email": email,
            "recovery_email": recovery_email,
            "user_id": user_id,
        },
    )
    conn.commit()


def update_password(conn, user_id: int, new_password_hash: str):
    """
    Update the user's password hash.
    """
    sql = """
        UPDATE app_user
        SET password_hash = :password_hash
        WHERE id = :user_id
    """
    conn.execute(
        text(sql),
        {"password_hash": new_password_hash, "user_id": user_id},
    )
    conn.commit()


def update_weight_unit(conn, user_id: int, weight_unit: str):
    """
    Update the user's preferred weight unit ('lb' or 'kg').
    """
    sql = """
        UPDATE app_user
        SET weight_unit = :weight_unit
        WHERE id = :user_id
    """
    conn.execute(text(sql), {"weight_unit": weight_unit, "user_id": user_id})
    conn.commit()


def update_week_start(conn, user_id: int, week_start: str):
    """
    Update the user's preferred start day of week ('sun' or 'mon').
    """
    sql = """
        UPDATE app_user
        SET week_start = :week_start
        WHERE id = :user_id
    """
    conn.execute(text(sql), {"week_start": week_start, "user_id": user_id})
    conn.commit()


def enable_totp(conn, user_id: int, secret: str):
    """
    Set the TOTP secret and mark 2FA as enabled.
    """
    sql = """
        UPDATE app_user
        SET totp_secret = :secret, totp_enabled = TRUE
        WHERE id = :user_id
    """
    conn.execute(text(sql), {"secret": secret, "user_id": user_id})
    conn.commit()
