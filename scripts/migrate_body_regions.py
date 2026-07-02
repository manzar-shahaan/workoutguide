import sys
from pathlib import Path

from sqlalchemy import text

# Ensure project root is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn
from utils.body_regions import REGIONS


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


def migrate_body_regions():
    conn = get_conn()
    try:
        if not _table_exists(conn, "body_region"):
            conn.execute(
                text(
                    """
                    CREATE TABLE body_region (
                        slug TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        view TEXT NOT NULL
                    )
                    """
                )
            )

        if not _table_exists(conn, "exercise_catalog_region"):
            conn.execute(
                text(
                    """
                    CREATE TABLE exercise_catalog_region (
                        exercise_catalog_id INTEGER NOT NULL,
                        region_slug TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'primary',
                        PRIMARY KEY (exercise_catalog_id, region_slug),
                        FOREIGN KEY (exercise_catalog_id) REFERENCES exercise_catalog (id) ON DELETE CASCADE,
                        FOREIGN KEY (region_slug) REFERENCES body_region (slug)
                    )
                    """
                )
            )

        if not _table_exists(conn, "suggested_exercise"):
            conn.execute(
                text(
                    """
                    CREATE TABLE suggested_exercise (
                        id SERIAL PRIMARY KEY,
                        wger_id INTEGER UNIQUE,
                        name TEXT NOT NULL,
                        image_path TEXT,
                        license_author TEXT,
                        license_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )

        if not _table_exists(conn, "suggested_exercise_region"):
            conn.execute(
                text(
                    """
                    CREATE TABLE suggested_exercise_region (
                        suggested_exercise_id INTEGER NOT NULL,
                        region_slug TEXT NOT NULL,
                        role TEXT NOT NULL DEFAULT 'primary',
                        PRIMARY KEY (suggested_exercise_id, region_slug),
                        FOREIGN KEY (suggested_exercise_id) REFERENCES suggested_exercise (id) ON DELETE CASCADE,
                        FOREIGN KEY (region_slug) REFERENCES body_region (slug)
                    )
                    """
                )
            )

        if not _column_exists(conn, "exercise_catalog", "suggested_exercise_id"):
            conn.execute(
                text(
                    "ALTER TABLE exercise_catalog ADD COLUMN suggested_exercise_id INTEGER REFERENCES suggested_exercise (id)"
                )
            )

        if not _column_exists(conn, "app_user", "body_model"):
            conn.execute(
                text("ALTER TABLE app_user ADD COLUMN body_model TEXT DEFAULT 'male'")
            )

        for slug, name, view, _category in REGIONS:
            conn.execute(
                text(
                    """
                    INSERT INTO body_region (slug, name, view)
                    VALUES (:slug, :name, :view)
                    ON CONFLICT (slug) DO UPDATE SET name = :name, view = :view
                    """
                ),
                {"slug": slug, "name": name, "view": view},
            )

        conn.commit()
    finally:
        conn.close()

    print("✅ body_region, exercise_catalog_region, suggested_exercise tables ensured + regions seeded")


if __name__ == "__main__":
    migrate_body_regions()
