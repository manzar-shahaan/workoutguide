"""
Phase 1 of the modality -> metric_type + tags split.

Adds the descriptive-tag system alongside the existing modality/
cardio_target columns (additive, safe to run before any UI change):
  - `tag` table (curated vocab from utils/tags.py) + `exercise_catalog_tag`
    join
  - `exercise_catalog.metric_type` ('resistance' | 'endurance')

Then backfills, with zero data loss:
  - metric_type: 'cardio' modality -> 'endurance'; everything else ->
    'resistance'
  - tags: one tag matching the old modality (strength/cardio/mobility/
    plyometrics), plus the cardio_target (steady/hiit/intervals/sprints)
    folded in as its own tag

Idempotent -- checks existence before each change and only backfills rows
that don't yet have a metric_type/tags set.

Usage:
    python scripts/migrate_tags.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn
from utils.tags import TAGS


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


def migrate_tags():
    conn = get_conn()
    try:
        # --- tables ---
        if not _table_exists(conn, "tag"):
            conn.execute(
                text(
                    """
                    CREATE TABLE tag (
                        slug TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        sort_order INTEGER NOT NULL DEFAULT 0
                    )
                    """
                )
            )
            print("created tag")
        else:
            print("tag already exists")

        if not _table_exists(conn, "exercise_catalog_tag"):
            conn.execute(
                text(
                    """
                    CREATE TABLE exercise_catalog_tag (
                        exercise_catalog_id INTEGER NOT NULL,
                        tag_slug TEXT NOT NULL,
                        PRIMARY KEY (exercise_catalog_id, tag_slug),
                        FOREIGN KEY (exercise_catalog_id) REFERENCES exercise_catalog (id) ON DELETE CASCADE,
                        FOREIGN KEY (tag_slug) REFERENCES tag (slug)
                    )
                    """
                )
            )
            print("created exercise_catalog_tag")
        else:
            print("exercise_catalog_tag already exists")

        # --- seed / refresh vocabulary ---
        for slug, name, sort_order in TAGS:
            conn.execute(
                text(
                    """
                    INSERT INTO tag (slug, name, sort_order)
                    VALUES (:slug, :name, :sort_order)
                    ON CONFLICT (slug) DO UPDATE SET name = :name, sort_order = :sort_order
                    """
                ),
                {"slug": slug, "name": name, "sort_order": sort_order},
            )
        print(f"seeded {len(TAGS)} tags")

        # --- metric_type column ---
        if not _column_exists(conn, "exercise_catalog", "metric_type"):
            conn.execute(
                text("ALTER TABLE exercise_catalog ADD COLUMN metric_type TEXT NOT NULL DEFAULT 'resistance'")
            )
            print("added exercise_catalog.metric_type")
        else:
            print("exercise_catalog.metric_type already exists")
        conn.commit()

        # --- backfill metric_type + tags from modality/cardio_target ---
        # Only run while the legacy columns still exist (i.e. before
        # migrate_drop_modality.py). After they're dropped this is skipped.
        if _column_exists(conn, "exercise_catalog", "modality"):
            rows = conn.execute(
                text("SELECT id, modality, cardio_target FROM exercise_catalog")
            ).mappings().all()

            metric_updates = 0
            tag_inserts = 0
            for row in rows:
                modality = row["modality"] or "strength"
                cardio_target = row["cardio_target"]

                metric_type = "endurance" if modality == "cardio" else "resistance"
                conn.execute(
                    text("UPDATE exercise_catalog SET metric_type = :mt WHERE id = :id"),
                    {"mt": metric_type, "id": row["id"]},
                )
                metric_updates += 1

                # The modality itself becomes a tag, plus cardio_target if set.
                slugs = [modality]
                if cardio_target:
                    slugs.append(cardio_target)
                for slug in slugs:
                    result = conn.execute(
                        text(
                            """
                            INSERT INTO exercise_catalog_tag (exercise_catalog_id, tag_slug)
                            VALUES (:id, :slug)
                            ON CONFLICT DO NOTHING
                            """
                        ),
                        {"id": row["id"], "slug": slug},
                    )
                    tag_inserts += result.rowcount or 0

            conn.commit()
            print(f"backfilled metric_type on {metric_updates} row(s), inserted {tag_inserts} tag link(s)")
        else:
            print("modality column already dropped -- skipping backfill")
    finally:
        conn.close()


if __name__ == "__main__":
    migrate_tags()
