"""
One-time (re-runnable) import of exercises from the public wger.de API
(CC-BY-SA 4.0 content) into `suggested_exercise` / `suggested_exercise_region`.

These are exercises the user hasn't logged yet -- shown de-emphasized below
their own history in the region-tap shortlist. Only imports exercises that
have an English name, at least one image, and at least one muscle we can
map to one of our body regions (utils.body_regions.WGER_MUSCLE_TO_REGION);
everything else is skipped as not useful for the map.

Usage:
    python scripts/import_wger_exercises.py [--max N]
"""

import argparse
import sys
import time
import urllib.request
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn
from utils.body_regions import REGION_NAME_KEYWORDS, WGER_MUSCLE_TO_REGION

API_BASE = "https://wger.de/api/v2/exerciseinfo/?format=json&language=2&limit=100"
ENGLISH_LANGUAGE_ID = 2
IMAGE_DIR = ROOT / "app" / "web" / "static" / "suggested"
USER_AGENT = "workoutguide-import-script/1.0 (personal self-hosted app)"


def _fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as resp:
        import json

        return json.loads(resp.read().decode("utf-8"))


def _english_name(exercise: dict) -> str | None:
    for translation in exercise.get("translations", []):
        if translation.get("language") == ENGLISH_LANGUAGE_ID:
            name = (translation.get("name") or "").strip()
            return name or None
    return None


def _regions_for(exercise: dict, name: str) -> list[tuple[str, str]]:
    seen = set()
    regions = []
    for muscle in exercise.get("muscles", []):
        slug = WGER_MUSCLE_TO_REGION.get(muscle.get("id"))
        if slug and slug not in seen:
            seen.add(slug)
            regions.append((slug, "primary"))
    for muscle in exercise.get("muscles_secondary", []):
        slug = WGER_MUSCLE_TO_REGION.get(muscle.get("id"))
        if slug and slug not in seen:
            seen.add(slug)
            regions.append((slug, "secondary"))

    # wger's 15 muscles don't cover forearm/lower-back/adductor/abductors/
    # back-deltoids at all -- catch those from the exercise name instead.
    name_lower = name.lower()
    for slug, keywords in REGION_NAME_KEYWORDS.items():
        if slug in seen:
            continue
        if any(keyword in name_lower for keyword in keywords):
            seen.add(slug)
            role = "primary" if not regions else "secondary"
            regions.append((slug, role))

    return regions


def _best_image(exercise: dict) -> dict | None:
    images = exercise.get("images") or []
    if not images:
        return None
    for image in images:
        if image.get("is_main"):
            return image
    return images[0]


def _download_image(url: str, dest: Path) -> bool:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=30) as resp:
            dest.write_bytes(resp.read())
        return True
    except Exception as exc:  # noqa: BLE001 - best-effort import, keep going
        print(f"  ! image download failed for {url}: {exc}")
        return False


def _upsert_suggested_exercise(conn, *, wger_id, name, image_path, license_author, license_name):
    row = conn.execute(
        text(
            """
            INSERT INTO suggested_exercise (wger_id, name, image_path, license_author, license_name)
            VALUES (:wger_id, :name, :image_path, :license_author, :license_name)
            ON CONFLICT (wger_id) DO UPDATE SET
                name = :name,
                image_path = :image_path,
                license_author = :license_author,
                license_name = :license_name
            RETURNING id
            """
        ),
        {
            "wger_id": wger_id,
            "name": name,
            "image_path": image_path,
            "license_author": license_author,
            "license_name": license_name,
        },
    )
    return row.scalar_one()


def import_wger_exercises(max_count: int | None = None):
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    conn = get_conn()
    imported = 0
    skipped_no_name = 0
    skipped_no_region = 0
    skipped_no_image = 0

    try:
        url = API_BASE
        while url:
            page = _fetch_json(url)
            for exercise in page["results"]:
                if max_count is not None and imported >= max_count:
                    url = None
                    break

                wger_id = exercise["id"]

                name = _english_name(exercise)
                if not name:
                    skipped_no_name += 1
                    continue

                regions = _regions_for(exercise, name)
                if not regions:
                    skipped_no_region += 1
                    continue

                image = _best_image(exercise)
                if not image:
                    skipped_no_image += 1
                    continue

                image_url = (image.get("thumbnails") or {}).get("small") or image["image"]
                dest = IMAGE_DIR / f"{wger_id}.png"
                if not dest.exists():
                    if not _download_image(image_url, dest):
                        continue
                    time.sleep(0.05)

                suggested_id = _upsert_suggested_exercise(
                    conn,
                    wger_id=wger_id,
                    name=name,
                    image_path=f"suggested/{wger_id}.png",
                    license_author=exercise.get("license_author") or None,
                    license_name=(exercise.get("license") or {}).get("short_name"),
                )

                conn.execute(
                    text("DELETE FROM suggested_exercise_region WHERE suggested_exercise_id = :id"),
                    {"id": suggested_id},
                )
                for slug, role in regions:
                    conn.execute(
                        text(
                            """
                            INSERT INTO suggested_exercise_region (suggested_exercise_id, region_slug, role)
                            VALUES (:id, :slug, :role)
                            """
                        ),
                        {"id": suggested_id, "slug": slug, "role": role},
                    )

                conn.commit()
                imported += 1
                print(f"  + {name} ({', '.join(s for s, _ in regions)})")

            if url is None:
                break
            url = page.get("next")
    finally:
        conn.close()

    print(
        f"\n✅ imported {imported} exercises "
        f"(skipped: {skipped_no_name} no English name, "
        f"{skipped_no_region} no mappable muscle, "
        f"{skipped_no_image} no image)"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=None, help="stop after importing N exercises (for testing)")
    args = parser.parse_args()
    import_wger_exercises(max_count=args.max)
