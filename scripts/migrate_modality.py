"""
Adds modality (strength/cardio/mobility/plyometrics) + cardio_target to
exercise_catalog, backfills modality from the current muscle category,
and loosens the schema so an exercise is no longer required to belong to
a muscle group -- classification now comes from modality + body-region
tags (or cardio_target for cardio), matching how the muscle-map picker
already works.

Safety: tightening the uniqueness constraint from (user, muscle, name) to
(user, name) only works if no user has the same exercise name filed under
two different muscle categories. This script checks for that first and
refuses to touch the constraint if it finds any -- resolve those (rename
or merge one of the pair) and re-run.

Re-running is a no-op once modality/cardio_target exist and the
constraint is already (user, name).

Usage:
    python scripts/migrate_modality.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn

CARDIO_TARGET_KEYWORDS = {
    "sprints": ["sprint"],
    "hiit": ["hiit"],
    "intervals": ["interval"],
}


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


def _guess_cardio_target(name: str) -> str:
    name_lower = name.lower()
    for target, keywords in CARDIO_TARGET_KEYWORDS.items():
        if any(keyword in name_lower for keyword in keywords):
            return target
    return "steady"


def _check_name_collisions(conn) -> list[dict]:
    rows = conn.execute(
        text(
            """
            SELECT user_id, lower(name) AS lname, count(DISTINCT muscle_id) AS distinct_muscles,
                   array_agg(DISTINCT muscle_id) AS muscle_ids
            FROM exercise_catalog
            GROUP BY user_id, lower(name)
            HAVING count(DISTINCT muscle_id) > 1
            """
        )
    ).mappings().all()
    return list(rows)


def migrate_modality():
    conn = get_conn()
    try:
        columns = _columns(conn, "exercise_catalog")

        if "modality" not in columns:
            conn.execute(text("ALTER TABLE exercise_catalog ADD COLUMN modality TEXT NOT NULL DEFAULT 'strength'"))
            conn.execute(text("ALTER TABLE exercise_catalog ADD COLUMN cardio_target TEXT"))
            conn.commit()
            print("added modality + cardio_target columns")

            rows = conn.execute(
                text(
                    """
                    SELECT ec.id, ec.name
                    FROM exercise_catalog ec
                    JOIN muscle m ON m.id = ec.muscle_id
                    WHERE m.name = 'cardio'
                    """
                )
            ).mappings().all()
            for row in rows:
                conn.execute(
                    text(
                        """
                        UPDATE exercise_catalog
                        SET modality = 'cardio', cardio_target = :target
                        WHERE id = :id
                        """
                    ),
                    {"id": row["id"], "target": _guess_cardio_target(row["name"])},
                )
            conn.commit()
            print(f"backfilled modality=cardio for {len(rows)} row(s)")
        else:
            print("modality/cardio_target already present, nothing to backfill")

        columns = _columns(conn, "exercise_catalog")
        muscle_id_nullable = conn.execute(
            text(
                """
                SELECT is_nullable FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'exercise_catalog' AND column_name = 'muscle_id'
                """
            )
        ).scalar_one()
        if muscle_id_nullable == "NO":
            conn.execute(text("ALTER TABLE exercise_catalog ALTER COLUMN muscle_id DROP NOT NULL"))
            conn.commit()
            print("made muscle_id nullable")
        else:
            print("muscle_id already nullable")

        # Tighten the unique constraint, but only if it's safe to do so.
        constraint_row = conn.execute(
            text(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'exercise_catalog'::regclass
                  AND contype = 'u'
                  AND conname != 'exercise_catalog_user_id_name_key'
                """
            )
        ).mappings().fetchone()

        if constraint_row is not None:
            collisions = _check_name_collisions(conn)
            if collisions:
                print("REFUSING to tighten unique constraint -- found name collisions across muscle groups:")
                for row in collisions:
                    print(f"  user {row['user_id']}: '{row['lname']}' exists under muscle_ids {row['muscle_ids']}")
                print("Resolve these (rename or merge one of each pair) and re-run this script.")
                return

            conn.execute(text(f"ALTER TABLE exercise_catalog DROP CONSTRAINT {constraint_row['conname']}"))
            conn.execute(
                text(
                    "ALTER TABLE exercise_catalog ADD CONSTRAINT exercise_catalog_user_id_name_key UNIQUE (user_id, name)"
                )
            )
            conn.commit()
            print(f"dropped old constraint '{constraint_row['conname']}', added (user_id, name)")
        else:
            print("unique constraint already (user_id, name)")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_modality()
