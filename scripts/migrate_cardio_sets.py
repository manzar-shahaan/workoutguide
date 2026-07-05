"""
Adds cardio metric columns: exercise_set gets duration_seconds/distance/
distance_unit (per interval); exercise gets total_duration_seconds/
total_distance/distance_unit (rollups, same pattern as the existing
weight_used/num_of_sets/avg_reps/max_reps columns). Strength/mobility/
plyometrics rows leave these NULL; cardio rows leave weight_used/reps NULL.

Re-runnable -- checks column existence before each ALTER.

Usage:
    python scripts/migrate_cardio_sets.py
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


def _add_column(conn, table: str, column: str, ddl_type: str) -> None:
    if _column_exists(conn, table, column):
        print(f"{table}.{column} already exists")
        return
    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl_type}"))
    conn.commit()
    print(f"added {table}.{column}")


def _is_nullable(conn, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT is_nullable FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = :table AND column_name = :column
            """
        ),
        {"table": table, "column": column},
    ).fetchone()
    return row is not None and row[0] == "YES"


def migrate_cardio_sets():
    conn = get_conn()
    try:
        _add_column(conn, "exercise_set", "duration_seconds", "INTEGER")
        _add_column(conn, "exercise_set", "distance", "DOUBLE PRECISION")
        _add_column(conn, "exercise_set", "distance_unit", "TEXT")

        _add_column(conn, "exercise", "total_duration_seconds", "INTEGER")
        _add_column(conn, "exercise", "total_distance", "DOUBLE PRECISION")
        _add_column(conn, "exercise", "distance_unit", "TEXT")

        # Cardio rows have no weight unit -- exercise.weight_unit predates
        # cardio and was NOT NULL, which would reject every cardio insert.
        if _is_nullable(conn, "exercise", "weight_unit"):
            print("exercise.weight_unit already nullable")
        else:
            conn.execute(text("ALTER TABLE exercise ALTER COLUMN weight_unit DROP NOT NULL"))
            conn.commit()
            print("dropped NOT NULL on exercise.weight_unit")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_cardio_sets()
