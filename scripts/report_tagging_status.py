"""
Read-only report on exercise_catalog classification under the
metric_type + descriptive-tags model.

Two independent things are reported:
- Region tagging (actionable): resistance exercises with no body-region
  tags don't show up in the muscle-map shortlist or count toward
  freshness, so these are worth tagging via the add/edit form.
- Descriptive tags (informational only): tags are optional by design, so
  an untagged entry isn't a problem -- this is just visibility into how
  much of the catalog has them, e.g. before relying on tag-based
  analytics like "minutes of cardio this week."

Usage:
    docker compose exec app python3 scripts/report_tagging_status.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn


def report_tagging_status():
    conn = get_conn()
    try:
        metric_summary = conn.execute(
            text(
                """
                SELECT metric_type, COUNT(*) AS n
                FROM exercise_catalog
                GROUP BY metric_type
                ORDER BY metric_type
                """
            )
        ).mappings().all()

        untagged_regions = conn.execute(
            text(
                """
                SELECT ec.id, ec.name
                FROM exercise_catalog ec
                WHERE ec.metric_type = 'resistance'
                  AND NOT EXISTS (
                    SELECT 1 FROM exercise_catalog_region r
                    WHERE r.exercise_catalog_id = ec.id
                  )
                ORDER BY ec.name
                """
            )
        ).mappings().all()

        untagged_descriptive = conn.execute(
            text(
                """
                SELECT ec.id, ec.name, ec.metric_type
                FROM exercise_catalog ec
                WHERE NOT EXISTS (
                    SELECT 1 FROM exercise_catalog_tag t
                    WHERE t.exercise_catalog_id = ec.id
                )
                ORDER BY ec.metric_type, ec.name
                """
            )
        ).mappings().all()

        resistance_total = conn.execute(
            text("SELECT COUNT(*) FROM exercise_catalog WHERE metric_type = 'resistance'")
        ).scalar()
        catalog_total = conn.execute(text("SELECT COUNT(*) FROM exercise_catalog")).scalar()
    finally:
        conn.close()

    print(f"{'metric_type':<14}{'count':<6}")
    print("-" * 20)
    for row in metric_summary:
        print(f"{row['metric_type']:<14}{row['n']:<6}")

    print(f"\nResistance exercises with no body-region tags: {len(untagged_regions)} of {resistance_total}")
    if untagged_regions:
        print(f"{'id':<6}{'name'}")
        for row in untagged_regions:
            print(f"{row['id']:<6}{row['name']}")

    print(f"\n(Informational) Exercises with no descriptive tags: {len(untagged_descriptive)} of {catalog_total}")
    if untagged_descriptive:
        print(f"{'id':<6}{'metric_type':<14}{'name'}")
        for row in untagged_descriptive:
            print(f"{row['id']:<6}{row['metric_type']:<14}{row['name']}")


if __name__ == "__main__":
    report_tagging_status()
