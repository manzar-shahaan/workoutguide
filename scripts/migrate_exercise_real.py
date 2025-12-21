import sys
from pathlib import Path

from sqlalchemy import text

# Ensure project root is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn

LB_TO_KG = 0.45359237


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


def migrate_exercise_weight_to_real():
    """
    Legacy migration helper:
    - add weight_unit and weight_used_kg if missing
    - backfill weight_used_kg for rows with weight_used
    """
    conn = get_conn()
    try:
        if not _column_exists(conn, "exercise", "weight_unit"):
            conn.execute(
                text("ALTER TABLE exercise ADD COLUMN weight_unit TEXT NOT NULL DEFAULT 'lb'")
            )
        if not _column_exists(conn, "exercise", "weight_used_kg"):
            conn.execute(text("ALTER TABLE exercise ADD COLUMN weight_used_kg DOUBLE PRECISION"))

        conn.execute(
            text(
                """
                UPDATE exercise
                SET weight_used_kg = CASE
                    WHEN weight_used IS NULL THEN NULL
                    WHEN weight_unit = 'kg' THEN weight_used
                    ELSE weight_used * :lb_to_kg
                END
                WHERE weight_used_kg IS NULL
                """
            ),
            {"lb_to_kg": LB_TO_KG},
        )
        conn.commit()
    finally:
        conn.close()

    print("✅ exercise weight unit columns ensured and normalized values backfilled")


if __name__ == "__main__":
    migrate_exercise_weight_to_real()
