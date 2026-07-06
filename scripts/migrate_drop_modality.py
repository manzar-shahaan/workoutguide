"""
Phase 3 of the modality -> metric_type + tags split: drops the now-unused
exercise_catalog.modality and cardio_target columns.

Run only AFTER migrate_tags.py (Phase 1) has been applied and the app has
been running on metric_type + tags -- migrate_tags.py backfills from these
columns, so dropping them first would lose the classification. Nothing in
the app reads modality/cardio_target anymore once Phase 2 shipped.

Idempotent -- checks existence before each drop.

Usage:
    python scripts/migrate_drop_modality.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn


def _column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).fetchone()
    return row is not None


def migrate_drop_modality():
    conn = get_conn()
    try:
        for column in ("modality", "cardio_target"):
            if _column_exists(conn, "exercise_catalog", column):
                conn.execute(text(f"ALTER TABLE exercise_catalog DROP COLUMN {column}"))
                conn.commit()
                print(f"dropped exercise_catalog.{column}")
            else:
                print(f"exercise_catalog.{column} already gone")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_drop_modality()
