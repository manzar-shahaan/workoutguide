"""
One-off: classify the exercise_catalog entries the fuzzy-match backfill
couldn't confidently place (plus a couple of modality corrections), now
that exercises are classified by modality + either body regions
(strength/mobility/plyometrics) or a cardio_target (cardio) instead of a
single muscle group. tag_regions/set_modality fully replace each entry's
state, so re-running just re-applies these.

Run once, then delete (this file is personal data, not repo content):
    docker compose exec app python3 scripts/tag_my_exercises.py
"""

import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn
from app.db.repositories import exercise_catalog as ec_repo

# catalog name (lowercased, as stored) -> regions in priority order.
# Strength/mobility/plyometrics are all classified by body region.
REGION_TAGS = {
    "hanging leg raises": ["abs", "quadriceps"],
    "lower abs": ["abs"],
    "twists": ["obliques", "abs"],
    "upper": ["abs"],                              # seated weighted crunch machine
    "db skull crushers": ["triceps"],
    "tricep overhead ext": ["triceps"],
    "waiter carry": ["front-deltoids", "abs"],     # overhead loaded carry
    "seated rows": ["upper-back", "biceps"],
    "hamstring curl": ["hamstring"],
    "hip thrusts": ["gluteal", "hamstring"],
    "low lat raise": ["front-deltoids"],           # cable lateral raise
    "shoulder low": ["front-deltoids"],            # cable lateral raise
    "shoulder db raises": ["front-deltoids", "triceps"],  # DB shoulder press
    "chin up": ["biceps", "upper-back"],           # biceps now primary
    "squats": ["quadriceps", "gluteal", "abs"],    # quads now primary (was gluteal, abs)
    "jumping jacks": ["quadriceps", "calves"],     # also modality=plyometrics, see below
}

# catalog name -> modality, for entries that aren't plain strength.
# Cardio entries get no region tags at all -- cardio_target is the only
# classification, so a run stops counting toward leg freshness.
MODALITY = {
    "cycle": ("cardio", "steady"),
    "running": ("cardio", "steady"),
    "treadmill run": ("cardio", "steady"),
    "jumping jacks": ("plyometrics", None),
}


def tag_my_exercises():
    conn = get_conn()
    tagged, missing = 0, []
    try:
        all_names = set(REGION_TAGS) | set(MODALITY)
        for name in all_names:
            rows = conn.execute(
                text("SELECT id FROM exercise_catalog WHERE lower(name) = :name"),
                {"name": name},
            ).mappings().all()
            if not rows:
                missing.append(name)
                continue

            modality, cardio_target = MODALITY.get(name, ("strength", None))
            regions = [] if modality == "cardio" else REGION_TAGS.get(name, [])

            for row in rows:
                ec_repo.set_modality(conn, row["id"], modality, cardio_target, commit=False)
                ec_repo.tag_regions(conn, row["id"], regions, commit=False)
                tagged += 1
        conn.commit()
    finally:
        conn.close()

    print(f"tagged {tagged} catalog row(s)")
    if missing:
        print("NOT FOUND (name mismatch -- check spelling): " + ", ".join(missing))


if __name__ == "__main__":
    tag_my_exercises()
