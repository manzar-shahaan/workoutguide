# scripts/import_legacy.py
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Connection

# Make project root importable so "app" can be found when running this file directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn

DEFAULT_WEIGHT_UNIT = "lb"
LB_TO_KG = 0.45359237


def column_exists(conn: Connection, table: str, column: str) -> bool:
    """Return True if a column exists on a table."""
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


def get_or_create_workout(conn: Connection, user_id: int, date: str) -> int:
    """
    Get an existing workout for (user_id, date) or create one.
    We no longer set workout.notes here; notes stay on exercises.
    """
    row = conn.execute(
        text("SELECT id FROM workout WHERE user_id = :user_id AND date = :date"),
        {"user_id": user_id, "date": date},
    ).mappings().fetchone()

    if row:
        return row["id"]

    result = conn.execute(
        text("INSERT INTO workout (date, user_id) VALUES (:date, :user_id) RETURNING id"),
        {"date": date, "user_id": user_id},
    )
    return result.scalar_one()


def get_or_create_muscle(conn: Connection, user_id: int, name: str) -> int:
    """
    Normalize muscle name to lowercase and either fetch or create it.
    """
    name_norm = (name or "").strip().lower()
    if not name_norm:
        name_norm = "unknown"

    row = conn.execute(
        text(
            """
            SELECT id
            FROM muscle
            WHERE user_id = :user_id AND name = :name
            """
        ),
        {"user_id": user_id, "name": name_norm},
    ).mappings().fetchone()
    if row:
        return row["id"]

    result = conn.execute(
        text(
            """
            INSERT INTO muscle (user_id, name, is_default, active)
            VALUES (:user_id, :name, FALSE, TRUE)
            RETURNING id
            """
        ),
        {"user_id": user_id, "name": name_norm},
    )
    return result.scalar_one()


def parse_weight_to_real(raw: Any) -> float | None:
    """
    Convert the legacy 'weights' field into a REAL.

    Accepts:
      - numbers: 26, 26.46
      - strings: "26", "26.46", "  26.46  "
    Returns:
      - float value when parseable
      - None when empty/missing/invalid
    """
    if raw is None:
        return None

    if isinstance(raw, (int, float)):
        return float(raw)

    raw_str = str(raw).strip()
    if raw_str == "" or raw_str.lower() in ("null", "none", "undefined"):
        return None

    try:
        return float(raw_str)
    except ValueError:
        return None


def weight_to_kg(weight_used: float | None, weight_unit: str) -> float | None:
    if weight_used is None:
        return None
    if weight_unit == "kg":
        return float(weight_used)
    if weight_unit == "lb":
        return float(weight_used) * LB_TO_KG
    return None


def insert_exercise(
    conn: Connection,
    workout_id: int,
    weight_used: float | None,
    weight_unit: str,
    weight_used_kg: float | None,
    num_sets: int | None,
    notes: str | None,
) -> int:
    """
    Insert an exercise row and return its id.
    weight_used is REAL; num_sets and notes can be NULL.
    """
    result = conn.execute(
        text(
            """
            INSERT INTO exercise (
                weight_used, weight_unit, weight_used_kg, num_of_sets, workout_id, notes
            )
            VALUES (:weight_used, :weight_unit, :weight_used_kg, :num_sets, :workout_id, :notes)
            RETURNING id
            """
        ),
        {
            "weight_used": weight_used,
            "weight_unit": weight_unit,
            "weight_used_kg": weight_used_kg,
            "num_sets": num_sets,
            "workout_id": workout_id,
            "notes": notes,
        },
    )
    return result.scalar_one()



def link_muscle_exercise(conn: Connection, muscle_id: int, exercise_id: int) -> None:
    """
    Link a muscle to an exercise via the join table.
    Uses ON CONFLICT DO NOTHING in case the pair already exists.
    """
    conn.execute(
        text(
            """
            INSERT INTO exercise_muscle (muscle_id, exercise_id)
            VALUES (:muscle_id, :exercise_id)
            ON CONFLICT DO NOTHING
            """
        ),
        {"muscle_id": muscle_id, "exercise_id": exercise_id},
    )



def load_json_any(path: Path) -> list[dict]:
    """
    Load legacy JSON file.
    Supports:
      - a JSON array: [ {...}, {...} ]
      - a single JSON object: {...}
      - newline-delimited JSON (NDJSON): one JSON object per line
    """
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []

    # Try to parse as a whole JSON document first
    try:
        parsed = json.loads(text)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            return [parsed]
    except json.JSONDecodeError:
        pass

    # Fallback: treat as NDJSON
    items: list[dict] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        items.append(json.loads(line))
    return items


def import_legacy(
    json_path: Path,
    user_id: int,
    dry_run: bool = False,
) -> dict:
    """
    Import legacy workout JSON into the new schema.

    Mapping rules:
      - Each entry has at least: date, type (Cardio/Strength), notes, maybe muscle/weights.
      - We do NOT store 'type' in the DB.
      - If type == 'Cardio':
          * ensure muscle 'cardio' exists
          * create an exercise with weight_used = NULL, num_of_sets = NULL
          * link that exercise to muscle 'cardio'
      - Else (Strength or no explicit type but muscle/weights present):
          * ensure muscle <muscle_name> (or 'unknown') exists
          * parse weights into REAL and store in exercise.weight_used
          * link exercise to that muscle

      - For each JSON entry, we attach it to a workout identified by (user_id, date).
    """
    items = load_json_any(json_path)

    conn = get_conn()
    trans = conn.begin()
    try:

        count_workouts_touched = 0
        count_exercises_created = 0
        seen_workout_keys: set[tuple[int, str]] = set()

        notes_col = column_exists(conn, "workout", "notes")

        for idx, item in enumerate(items, start=1):
            date = item.get("date")
            if not date:
                # If there's no date, we can't import this row meaningfully.
                # You could log or print this; for now, just skip.
                continue

            legacy_type_raw = item.get("type") or ""
            legacy_type = str(legacy_type_raw).strip().lower()

            notes = item.get("notes") or None
            muscle_name_raw = item.get("muscle") or ""
            muscle_name = str(muscle_name_raw).strip().lower()

            # 1) Ensure a workout for (user_id, date)
            w_id = get_or_create_workout(
                conn,
                user_id=user_id,
                date=date,
            )

            wk_key = (user_id, date)
            if wk_key not in seen_workout_keys:
                seen_workout_keys.add(wk_key)
                count_workouts_touched += 1

            # 2) Cardio mapping: type = 'cardio' → muscle 'cardio', weight_used = NULL
            if legacy_type == "cardio":
                m_id = get_or_create_muscle(conn, user_id, "cardio")
                weight_unit = DEFAULT_WEIGHT_UNIT
                weight_used_kg = weight_to_kg(None, weight_unit)
                ex_id = insert_exercise(
                    conn,
                    workout_id=w_id,
                    weight_used=None,   # REAL; stored as NULL
                    weight_unit=weight_unit,
                    weight_used_kg=weight_used_kg,
                    num_sets=None,
                    notes=notes,        # <- per-entry notes on the exercise
                )
                link_muscle_exercise(conn, m_id, ex_id)
                count_exercises_created += 1
                continue


            # 3) Strength / other physical entries:
            # We treat rows with a 'muscle' or 'weights' field as exercise entries.
            if muscle_name or ("weights" in item):
                m_id = get_or_create_muscle(conn, user_id, muscle_name or "unknown")
                weight_real = parse_weight_to_real(item.get("weights"))
                weight_unit = DEFAULT_WEIGHT_UNIT
                weight_used_kg = weight_to_kg(weight_real, weight_unit)
                ex_id = insert_exercise(
                    conn,
                    workout_id=w_id,
                    weight_used=weight_real,
                    weight_unit=weight_unit,
                    weight_used_kg=weight_used_kg,
                    num_sets=None,
                    notes=notes,        # <- notes for this specific strength entry
                )
                link_muscle_exercise(conn, m_id, ex_id)
                count_exercises_created += 1
                continue


            # 4) If neither cardio nor strength-like fields exist, we still keep the created workout,
            # but don't create an exercise. Could print/log a warning here if desired.

        if dry_run:
            trans.rollback()
        else:
            trans.commit()

        return {
            "dry_run": dry_run,
            "total_items": len(items),
            "workouts_touched": count_workouts_touched,
            "exercises_created": count_exercises_created,
            "notes_column_present": notes_col,
        }
    except Exception:
        trans.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import legacy workout JSON into the PostgreSQL database."
    )
    parser.add_argument(
        "--path",
        required=True,
        help="Path to the legacy JSON file",
    )
    parser.add_argument(
        "--user-id",
        required=True,
        type=int,
        help="User ID to attach imported workouts to",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and preview changes without committing them",
    )

    args = parser.parse_args()
    json_path = Path(args.path)

    if not json_path.exists():
        print(f"❌ File not found: {json_path}")
        sys.exit(1)

    result = import_legacy(
        json_path=json_path,
        user_id=args.user_id,
        dry_run=args.dry_run,
    )

    mode = "DRY RUN" if args.dry_run else "IMPORT"
    print(f"\n✅ {mode} complete for {json_path}")
    for k, v in result.items():
        print(f" - {k}: {v}")


if __name__ == "__main__":
    main()
