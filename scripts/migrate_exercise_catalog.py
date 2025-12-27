import sys
from pathlib import Path

from sqlalchemy import text

# Ensure project root is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn


def _table_exists(conn, table: str) -> bool:
    sql = """
        SELECT 1
        FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_name = :table
        LIMIT 1
    """
    row = conn.execute(text(sql), {"table": table}).fetchone()
    return row is not None


def _column_exists(conn, table: str, column: str) -> bool:
    sql = """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table
          AND column_name = :column
        LIMIT 1
    """
    row = conn.execute(text(sql), {"table": table, "column": column}).fetchone()
    return row is not None


def _constraint_exists(conn, table: str, constraint_name: str) -> bool:
    sql = """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema = 'public'
          AND table_name = :table
          AND constraint_name = :constraint_name
        LIMIT 1
    """
    row = conn.execute(
        text(sql),
        {"table": table, "constraint_name": constraint_name},
    ).fetchone()
    return row is not None


def migrate_exercise_catalog():
    conn = get_conn()
    try:
        if not _table_exists(conn, "exercise_catalog"):
            conn.execute(
                text(
                    """
                    CREATE TABLE exercise_catalog (
                        id SERIAL PRIMARY KEY,
                        user_id INTEGER NOT NULL,
                        muscle_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES app_user (id),
                        FOREIGN KEY (muscle_id) REFERENCES muscle (id),
                        UNIQUE (user_id, muscle_id, name)
                    )
                    """
                )
            )

        if not _column_exists(conn, "exercise", "exercise_catalog_id"):
            conn.execute(text("ALTER TABLE exercise ADD COLUMN exercise_catalog_id INTEGER"))
        if not _column_exists(conn, "exercise", "exercise_name"):
            conn.execute(text("ALTER TABLE exercise ADD COLUMN exercise_name TEXT"))

        fk_name = "exercise_exercise_catalog_id_fkey"
        if not _constraint_exists(conn, "exercise", fk_name):
            conn.execute(
                text(
                    """
                    ALTER TABLE exercise
                    ADD CONSTRAINT exercise_exercise_catalog_id_fkey
                    FOREIGN KEY (exercise_catalog_id)
                    REFERENCES exercise_catalog (id)
                    """
                )
            )

        conn.commit()
    finally:
        conn.close()

    print("✅ exercise_catalog table and exercise linkage columns ensured")


if __name__ == "__main__":
    migrate_exercise_catalog()
