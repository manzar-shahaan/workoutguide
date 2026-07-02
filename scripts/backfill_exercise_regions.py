"""
One-time (re-runnable) pass to tag pre-existing exercise_catalog rows with
body regions, by fuzzy-matching their names against the wger-sourced
suggested_exercise table. Run this after import_wger_exercises.py, and
again any time you want to re-check previously-unmatched exercise names
(e.g. after importing more suggestions).

Usage:
    python scripts/backfill_exercise_regions.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn
from app.db.repositories import exercise_catalog as exercise_catalog_repo


def backfill_exercise_regions():
    conn = get_conn()
    try:
        tagged = exercise_catalog_repo.backfill_regions_from_suggestions(conn)
    finally:
        conn.close()
    print(f"✅ tagged {tagged} previously-untagged exercise_catalog rows with regions")


if __name__ == "__main__":
    backfill_exercise_regions()
