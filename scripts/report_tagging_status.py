"""
Read-only report: how many exercise_catalog entries are tagged vs.
untagged under the modality/region model, broken down by modality.

"Tagged" means:
- cardio: cardio_target is set
- strength/mobility/plyometrics: has at least one exercise_catalog_region row

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
        summary = conn.execute(
            text(
                """
                SELECT
                    ec.modality,
                    CASE
                        WHEN ec.modality = 'cardio' THEN ec.cardio_target IS NOT NULL
                        ELSE EXISTS (
                            SELECT 1 FROM exercise_catalog_region r
                            WHERE r.exercise_catalog_id = ec.id
                        )
                    END AS tagged,
                    COUNT(*) AS n
                FROM exercise_catalog ec
                GROUP BY 1, 2
                ORDER BY 1, 2 DESC
                """
            )
        ).mappings().all()

        untagged = conn.execute(
            text(
                """
                SELECT ec.id, ec.name, ec.modality
                FROM exercise_catalog ec
                WHERE
                    (ec.modality = 'cardio' AND ec.cardio_target IS NULL)
                    OR (
                        ec.modality != 'cardio' AND NOT EXISTS (
                            SELECT 1 FROM exercise_catalog_region r
                            WHERE r.exercise_catalog_id = ec.id
                        )
                    )
                ORDER BY ec.modality, ec.name
                """
            )
        ).mappings().all()
    finally:
        conn.close()

    print(f"{'modality':<14}{'tagged':<10}{'count':<6}")
    print("-" * 30)
    total_tagged, total_untagged = 0, 0
    for row in summary:
        print(f"{row['modality']:<14}{str(row['tagged']):<10}{row['n']:<6}")
        if row["tagged"]:
            total_tagged += row["n"]
        else:
            total_untagged += row["n"]
    print("-" * 30)
    print(f"{'total tagged':<24}{total_tagged}")
    print(f"{'total untagged':<24}{total_untagged}")

    if untagged:
        print(f"\nUntagged entries ({len(untagged)}):")
        print(f"{'id':<6}{'modality':<14}{'name'}")
        for row in untagged:
            print(f"{row['id']:<6}{row['modality']:<14}{row['name']}")


if __name__ == "__main__":
    report_tagging_status()
