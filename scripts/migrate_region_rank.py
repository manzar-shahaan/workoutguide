"""
Converts exercise_catalog_region.role (text 'primary'/'secondary', which
the picker widget capped at 2 tags per exercise) to a rank integer (1, 2,
3, ...), so an exercise can be tagged with as many regions as it actually
trains, with tap order determining priority instead of a fixed binary
split.

'primary' -> rank 1, 'secondary' -> rank 2 (the only two values that
existed before this migration). Re-running is a no-op once the rank
column is in place.

Usage:
    python scripts/migrate_region_rank.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn


def _columns(conn, table: str) -> set[str]:
    rows = conn.execute(
        text(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table
            """
        ),
        {"table": table},
    ).scalars().all()
    return set(rows)


def migrate_region_rank():
    conn = get_conn()
    try:
        columns = _columns(conn, "exercise_catalog_region")

        if "rank" not in columns:
            conn.execute(text("ALTER TABLE exercise_catalog_region ADD COLUMN rank INTEGER"))
            conn.execute(
                text(
                    """
                    UPDATE exercise_catalog_region
                    SET rank = CASE WHEN role = 'primary' THEN 1 ELSE 2 END
                    """
                )
            )
            conn.execute(text("ALTER TABLE exercise_catalog_region ALTER COLUMN rank SET NOT NULL"))
            conn.execute(text("ALTER TABLE exercise_catalog_region ALTER COLUMN rank SET DEFAULT 1"))
            conn.commit()
            print("added rank column, backfilled from role")
        else:
            print("rank column already present, nothing to backfill")

        columns = _columns(conn, "exercise_catalog_region")
        if "role" in columns:
            conn.execute(text("ALTER TABLE exercise_catalog_region DROP COLUMN role"))
            conn.commit()
            print("dropped legacy role column")
        else:
            print("legacy role column already gone")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_region_rank()
