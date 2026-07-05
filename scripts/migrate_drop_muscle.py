"""
Phase 3 of the muscle -> modality/region cutover: drops the now-fully-
unused muscle system entirely -- exercise_catalog.muscle_id,
exercise_muscle, and muscle. Nothing in the app has read or written any
of these since the modality/region model shipped (Phase 2); this just
removes the dead weight.

Safe to run any time after migrate_modality.py (Phase 1/2) has been
applied and the app has been running on the region/modality model.
Idempotent -- checks existence before each drop.

Usage:
    python scripts/migrate_drop_muscle.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn


def _table_exists(conn, table: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = :table
            """
        ),
        {"table": table},
    ).fetchone()
    return row is not None


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


def migrate_drop_muscle():
    conn = get_conn()
    try:
        if _table_exists(conn, "exercise_muscle"):
            conn.execute(text("DROP TABLE exercise_muscle"))
            conn.commit()
            print("dropped exercise_muscle")
        else:
            print("exercise_muscle already gone")

        if _column_exists(conn, "exercise_catalog", "muscle_id"):
            conn.execute(text("ALTER TABLE exercise_catalog DROP COLUMN muscle_id"))
            conn.commit()
            print("dropped exercise_catalog.muscle_id")
        else:
            print("exercise_catalog.muscle_id already gone")

        if _table_exists(conn, "muscle"):
            conn.execute(text("DROP TABLE muscle"))
            conn.commit()
            print("dropped muscle")
        else:
            print("muscle already gone")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_drop_muscle()
