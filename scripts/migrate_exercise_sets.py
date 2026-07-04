"""
Adds exercise_set (per-set weight/reps) and backfills it from existing
exercise rows, so every exercise -- old and new -- has real set rows and
stats/volume/display code can read one source of truth instead of
branching on whether an exercise predates this feature.

Backfill approximation: num_of_sets rows at avg_reps (rounded). If
max_reps is recorded and higher than avg_reps, one set is bumped to
max_reps instead, so a session that was "4 sets, avg 8, max 10" doesn't
just flatten to four identical 8-rep sets -- the peak set is preserved.
This can't recover the *exact* original per-set reps (that data was never
captured), just a reasonable reconstruction. Re-running is a no-op for
exercises that already have set rows.

Usage:
    python scripts/migrate_exercise_sets.py
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
            LIMIT 1
            """
        ),
        {"table": table},
    ).fetchone()
    return row is not None


def _ensure_table(conn):
    if _table_exists(conn, "exercise_set"):
        return
    conn.execute(
        text(
            """
            CREATE TABLE exercise_set (
                id SERIAL PRIMARY KEY,
                exercise_id INTEGER NOT NULL,
                set_index INTEGER NOT NULL,
                weight_used DOUBLE PRECISION,
                weight_unit TEXT,
                weight_used_kg DOUBLE PRECISION,
                reps INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (exercise_id) REFERENCES exercise (id) ON DELETE CASCADE,
                UNIQUE (exercise_id, set_index)
            )
            """
        )
    )
    conn.commit()


def _backfill(conn) -> int:
    rows = conn.execute(
        text(
            """
            SELECT e.id, e.weight_used, e.weight_unit, e.weight_used_kg,
                   e.num_of_sets, e.avg_reps, e.max_reps
            FROM exercise e
            LEFT JOIN exercise_set s ON s.exercise_id = e.id
            WHERE s.id IS NULL
              AND e.num_of_sets IS NOT NULL
              AND e.num_of_sets > 0
            """
        )
    ).mappings().all()

    backfilled = 0
    for row in rows:
        num_sets = row["num_of_sets"]
        avg_reps = row["avg_reps"]
        max_reps = row["max_reps"]
        base_reps = round(avg_reps) if avg_reps is not None else None

        reps_per_set = [base_reps] * num_sets
        if max_reps is not None and base_reps is not None and max_reps > base_reps:
            reps_per_set[0] = max_reps  # preserve the peak set, not just the average

        for i, reps in enumerate(reps_per_set, start=1):
            conn.execute(
                text(
                    """
                    INSERT INTO exercise_set
                        (exercise_id, set_index, weight_used, weight_unit, weight_used_kg, reps)
                    VALUES (:exercise_id, :set_index, :weight_used, :weight_unit, :weight_used_kg, :reps)
                    ON CONFLICT (exercise_id, set_index) DO NOTHING
                    """
                ),
                {
                    "exercise_id": row["id"],
                    "set_index": i,
                    "weight_used": row["weight_used"],
                    "weight_unit": row["weight_unit"],
                    "weight_used_kg": row["weight_used_kg"],
                    "reps": reps,
                },
            )
        backfilled += 1

    conn.commit()
    return backfilled


def migrate_exercise_sets():
    conn = get_conn()
    try:
        _ensure_table(conn)
        backfilled = _backfill(conn)
    finally:
        conn.close()
    print(f"✅ exercise_set table ensured, backfilled {backfilled} exercises")


if __name__ == "__main__":
    migrate_exercise_sets()
