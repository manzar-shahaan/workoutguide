import argparse
import secrets
import string
import sys
from pathlib import Path

# Ensure project root is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn
from app.db.repositories import access_codes as access_codes_repo


ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _ensure_table(conn):
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS access_code (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            code TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            used_by_user_id INTEGER,
            used_at TIMESTAMP,
            FOREIGN KEY (used_by_user_id) REFERENCES app_user (id),
            UNIQUE (name)
        )
        """
    )
    conn.commit()


def _generate_code(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def main():
    parser = argparse.ArgumentParser(description="Generate a signup access code.")
    parser.add_argument("name", help="Label for who this code is for.")
    parser.add_argument("--length", type=int, default=12, help="Code length (default: 12).")
    args = parser.parse_args()

    name = args.name.strip()
    if not name:
        raise SystemExit("Name is required.")

    if args.length < 6 or args.length > 64:
        raise SystemExit("Length must be between 6 and 64.")

    conn = get_conn()
    try:
        _ensure_table(conn)
        existing = access_codes_repo.get_by_name(conn, name)
        if existing:
            status = "USED" if existing["used_by_user_id"] else "UNUSED"
            print(f"Name already has a code: {existing['code']} ({status})")
            return

        for _ in range(20):
            code = _generate_code(args.length)
            if access_codes_repo.get_by_code(conn, code):
                continue
            access_codes_repo.create_access_code(conn, name, code)
            print(code)
            return
    finally:
        conn.close()

    raise SystemExit("Unable to generate a unique access code. Try again.")


if __name__ == "__main__":
    main()
