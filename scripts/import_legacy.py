# scripts/import_legacy.py
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date as date_cls, datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.engine import Connection

# Make project root importable so "app" can be found when running this file directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn
from app.db.repositories import exercise_catalog as exercise_catalog_repo
from app.db.repositories import users as users_repo

DEFAULT_WEIGHT_UNIT = "lb"
LB_TO_KG = 0.45359237
VALID_WEIGHT_UNITS = {"lb", "kg"}
WEIGHT_RE = re.compile(r"^\s*([0-9]*\.?[0-9]+)\s*([a-zA-Z]*)\s*$")
SETS_RE = re.compile(r"\b\d+\s*x\s*\d+\b", re.IGNORECASE)
WEIGHT_TOKEN_RE = re.compile(r"\b\d+(\.\d+)?\s*(lb|lbs|kg|kgs)\b", re.IGNORECASE)
RPE_RE = re.compile(r"\brpe\s*\d+(\.\d+)?\b", re.IGNORECASE)
TEMPO_RE = re.compile(r"\btempo\s*\d+(-\d+){2,}\b", re.IGNORECASE)
EXERCISE_CLEAN_RE = re.compile(r"[^a-z\s]")
DEFAULT_STOPWORDS = {
    "plates",
    "plate",
    "bar",
    "barbell",
    "dumbbell",
    "dumbbells",
    "kettlebell",
    "kettlebells",
    "machine",
    "band",
    "bands",
    "cable",
    "assisted",
}
FUZZY_MATCH_THRESHOLD = 92

try:
    from rapidfuzz import fuzz as _fuzz
except Exception:  # pragma: no cover - optional dependency
    _fuzz = None


def _coerce_to_list(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("workouts", "entries", "data", "items"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    return []


def _parse_date(value: Any, tz: str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, date_cls) and not isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, datetime):
        dt = value
        if tz:
            tzinfo = ZoneInfo(tz)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=tzinfo)
            else:
                dt = dt.astimezone(tzinfo)
        return dt.date().isoformat()
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        try:
            return date_cls.fromisoformat(raw).isoformat()
        except ValueError:
            pass
        try:
            raw = raw.replace("Z", "+00:00")
            dt = datetime.fromisoformat(raw)
            if tz:
                tzinfo = ZoneInfo(tz)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=tzinfo)
                else:
                    dt = dt.astimezone(tzinfo)
            return dt.date().isoformat()
        except ValueError:
            return None
    return None


def _normalize_unit(unit: str | None) -> str | None:
    if not unit:
        return None
    norm = unit.strip().lower()
    if norm in ("lb", "lbs", "pound", "pounds"):
        return "lb"
    if norm in ("kg", "kgs", "kilogram", "kilograms"):
        return "kg"
    return None


def _parse_weight(
    value: Any,
    default_unit: str,
    strict: bool,
    unit_hint: str | None = None,
) -> tuple[float | None, str, str | None]:
    if value is None:
        return None, default_unit, None

    raw_value = value

    if isinstance(value, dict):
        raw_value = value.get("value", value.get("weight", value.get("weight_used")))
        unit_hint = unit_hint or value.get("unit", value.get("weight_unit"))

    if isinstance(raw_value, (int, float)):
        weight = float(raw_value)
        unit_norm = _normalize_unit(unit_hint) or default_unit
        if unit_norm not in VALID_WEIGHT_UNITS:
            if strict:
                return None, default_unit, "invalid weight unit"
            unit_norm = default_unit
        return weight, unit_norm, None

    raw_str = str(raw_value).strip()
    if raw_str == "" or raw_str.lower() in ("null", "none", "undefined"):
        return None, default_unit, None

    match = WEIGHT_RE.match(raw_str)
    if not match:
        return None, default_unit, "invalid weight"

    weight = float(match.group(1))
    unit_from_value = _normalize_unit(match.group(2)) if match.group(2) else None
    unit_norm = _normalize_unit(unit_hint) or unit_from_value or default_unit
    if unit_norm not in VALID_WEIGHT_UNITS:
        if strict:
            return None, default_unit, "invalid weight unit"
        unit_norm = default_unit
    return weight, unit_norm, None


def _parse_sets(value: Any, strict: bool) -> tuple[int | None, str | None]:
    if value is None:
        return None, None
    if isinstance(value, int):
        return value, None
    raw = str(value).strip()
    if not raw:
        return None, None
    try:
        return int(raw), None
    except ValueError:
        if strict:
            return None, "invalid num_of_sets"
        return None, None


def _normalize_muscles(value: Any) -> list[str]:
    if value is None:
        return []
    muscles: list[str] = []
    if isinstance(value, list):
        iterable = value
    else:
        iterable = [value]
    for item in iterable:
        if item is None:
            continue
        if isinstance(item, str):
            parts = item.split(",")
            for part in parts:
                name = part.strip().lower()
                if name:
                    muscles.append(name)
        else:
            name = str(item).strip().lower()
            if name:
                muscles.append(name)
    return muscles


def _clean_notes(value: Any) -> str | None:
    if value is None:
        return None
    raw = str(value).strip()
    return raw or None


def _extract_exercise_name(text: str | None) -> str | None:
    if not text:
        return None
    raw = text.lower()
    raw = WEIGHT_TOKEN_RE.sub(" ", raw)
    raw = SETS_RE.sub(" ", raw)
    raw = RPE_RE.sub(" ", raw)
    raw = TEMPO_RE.sub(" ", raw)
    tokens = []
    for part in re.split(r"[;,/|@\-]", raw):
        part = part.strip()
        if not part:
            continue
        tokens.append(part)
    if not tokens:
        return None
    candidate = max(tokens, key=len)
    candidate = EXERCISE_CLEAN_RE.sub(" ", candidate)
    words = [w for w in candidate.split() if w and w not in DEFAULT_STOPWORDS]
    if not words:
        return None
    return " ".join(words).strip() or None


def _normalize_exercise_name(value: str | None) -> str | None:
    if not value:
        return None
    name = value.strip().lower()
    return name or None


def _best_catalog_match(
    names: list[str],
    candidate: str,
) -> tuple[str | None, int]:
    if not names or not candidate or _fuzz is None:
        return None, 0
    candidate_norm = _normalize_exercise_name(candidate) or candidate
    best_name = None
    best_score = 0
    for name in names:
        score = _fuzz.token_set_ratio(candidate_norm, name)
        if score > best_score:
            best_score = score
            best_name = name
    return best_name, best_score


def _has_exercise_fields(item: dict) -> bool:
    keys = {
        "weights",
        "weight_used",
        "weight",
        "weight_unit",
        "num_of_sets",
        "num_sets",
        "sets",
        "muscle",
        "muscles",
    }
    return any(key in item for key in keys)


def _normalize_exercise(
    raw_ex: dict,
    default_unit: str,
    strict: bool,
    report: dict,
    idx: int,
) -> dict | None:
    notes = _clean_notes(raw_ex.get("notes"))
    exercise_name = _normalize_exercise_name(
        _clean_notes(raw_ex.get("exercise_name", raw_ex.get("exercise", raw_ex.get("name"))))
    )
    muscles = _normalize_muscles(raw_ex.get("muscles", raw_ex.get("muscle")))
    exercise_type = str(raw_ex.get("type") or "").strip().lower()
    if exercise_type == "cardio" and not muscles:
        muscles = ["cardio"]
    weight_value = raw_ex.get("weight_used", raw_ex.get("weights", raw_ex.get("weight")))
    weight_used, weight_unit, weight_error = _parse_weight(
        weight_value,
        default_unit,
        strict,
        unit_hint=raw_ex.get("weight_unit"),
    )
    num_sets, sets_error = _parse_sets(
        raw_ex.get("num_of_sets", raw_ex.get("num_sets", raw_ex.get("sets"))),
        strict,
    )

    if weight_error:
        report["warnings"].append({"index": idx, "reason": weight_error})
        if strict:
            return None
    if sets_error:
        report["warnings"].append({"index": idx, "reason": sets_error})
        if strict:
            return None

    return {
        "notes": notes,
        "exercise_name": exercise_name,
        "weight_used": weight_used,
        "weight_unit": weight_unit,
        "num_of_sets": num_sets,
        "muscles": muscles,
    }


def normalize_payload(
    payload: Any,
    *,
    default_unit: str,
    tz: str | None,
    strict: bool,
    source: str,
) -> tuple[list[dict], dict]:
    report: dict = {"skipped": [], "warnings": []}
    items = _coerce_to_list(payload)
    normalized: list[dict] = []

    for idx, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            report["skipped"].append({"index": idx, "reason": "invalid item type"})
            continue

        if source == "legacy":
            item_kind = "legacy"
        elif source == "generic":
            item_kind = "generic"
        else:
            if "exercises" in item or "workout" in item:
                item_kind = "generic"
            else:
                item_kind = "legacy"

        if item_kind == "generic":
            if "workout" in item and isinstance(item["workout"], dict):
                workout_item = dict(item["workout"])
                if "exercises" not in workout_item and isinstance(item.get("exercises"), list):
                    workout_item["exercises"] = item["exercises"]
            else:
                workout_item = item

            date_value = workout_item.get("date")
            date_str = _parse_date(date_value, tz)
            if not date_str:
                report["skipped"].append({"index": idx, "reason": "missing or invalid date"})
                continue

            workout_notes = _clean_notes(workout_item.get("notes"))
            exercises_raw = workout_item.get("exercises") or []
            exercises: list[dict] = []

            if isinstance(exercises_raw, list):
                for ex in exercises_raw:
                    if not isinstance(ex, dict):
                        report["warnings"].append({"index": idx, "reason": "invalid exercise type"})
                        if strict:
                            continue
                        else:
                            continue
                    ex_norm = _normalize_exercise(ex, default_unit, strict, report, idx)
                    if ex_norm:
                        exercises.append(ex_norm)
            elif exercises_raw:
                report["warnings"].append({"index": idx, "reason": "exercises not a list"})
                if strict:
                    continue

            normalized.append(
                {
                    "date": date_str,
                    "notes": workout_notes,
                    "exercises": exercises,
                }
            )
            continue

        # Legacy entry normalization
        date_value = item.get("date", item.get("workout_date"))
        date_str = _parse_date(date_value, tz)
        if not date_str:
            report["skipped"].append({"index": idx, "reason": "missing or invalid date"})
            continue

        legacy_type = str(item.get("type") or "").strip().lower()
        notes = _clean_notes(item.get("notes"))
        exercise_name = _normalize_exercise_name(
            _clean_notes(item.get("exercise_name", item.get("exercise")))
        )
        muscles = _normalize_muscles(item.get("muscle", item.get("muscles")))
        weight_value = item.get("weights", item.get("weight_used", item.get("weight")))
        weight_used, weight_unit, weight_error = _parse_weight(
            weight_value,
            default_unit,
            strict,
            unit_hint=item.get("weight_unit"),
        )
        num_sets, sets_error = _parse_sets(
            item.get("num_of_sets", item.get("num_sets", item.get("sets"))),
            strict,
        )

        if weight_error:
            report["warnings"].append({"index": idx, "reason": weight_error})
            if strict:
                continue
        if sets_error:
            report["warnings"].append({"index": idx, "reason": sets_error})
            if strict:
                continue

        has_exercise_fields = _has_exercise_fields(item)
        if legacy_type == "cardio" and not has_exercise_fields and notes:
            has_exercise_data = False
        else:
            has_exercise_data = has_exercise_fields or legacy_type == "cardio"
        exercises: list[dict] = []
        workout_notes = None

        if legacy_type == "cardio" and not muscles:
            muscles = ["cardio"]

        if has_exercise_data:
            exercises.append(
                {
                    "notes": notes,
                    "exercise_name": exercise_name,
                    "weight_used": weight_used,
                    "weight_unit": weight_unit,
                    "num_of_sets": num_sets,
                    "muscles": muscles,
                }
            )
        else:
            workout_notes = notes

        normalized.append(
            {
                "date": date_str,
                "notes": workout_notes,
                "exercises": exercises,
            }
        )

    return normalized, report


def get_or_create_workout(conn: Connection, user_id: int, date: str) -> tuple[int, bool]:
    """
    Get an existing workout for (user_id, date) or create one.
    Workout notes are appended separately when present.
    """
    row = conn.execute(
        text("SELECT id FROM workout WHERE user_id = :user_id AND date = :date"),
        {"user_id": user_id, "date": date},
    ).mappings().fetchone()

    if row:
        return row["id"], False

    result = conn.execute(
        text("INSERT INTO workout (date, user_id) VALUES (:date, :user_id) RETURNING id"),
        {"date": date, "user_id": user_id},
    )
    return result.scalar_one(), True


def append_workout_notes(conn: Connection, workout_id: int, notes: str | None) -> None:
    if not notes:
        return
    existing = conn.execute(
        text("SELECT notes FROM workout WHERE id = :id"),
        {"id": workout_id},
    ).mappings().fetchone()
    current = (existing or {}).get("notes")
    if current:
        combined = f"{current}\n{notes}"
    else:
        combined = notes
    conn.execute(
        text("UPDATE workout SET notes = :notes WHERE id = :id"),
        {"notes": combined, "id": workout_id},
    )


def infer_metric_type(muscles: list[str]) -> tuple[str, list[str]]:
    """
    Returns (metric_type, tags). Legacy free-text muscle names ("chest",
    "legs", "back"...) can't be reliably auto-mapped onto the fixed
    17-region taxonomy -- "arms" alone doesn't say biceps vs. triceps vs.
    forearm -- so region tagging for imported exercises is left for the
    user to do via the add/edit form's body-map picker. Cardio is the one
    signal legacy data reliably carries (the old app's "cardio" muscle
    bucket): those become endurance (duration/distance) + a [cardio] tag;
    everything else defaults to resistance with no tags.
    """
    if "cardio" in muscles:
        return "endurance", ["cardio"]
    return "resistance", []


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
    exercise_catalog_id: int | None,
    exercise_name: str | None,
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
                exercise_catalog_id,
                exercise_name,
                weight_used,
                weight_unit,
                weight_used_kg,
                num_of_sets,
                workout_id,
                notes
            )
            VALUES (
                :exercise_catalog_id,
                :exercise_name,
                :weight_used,
                :weight_unit,
                :weight_used_kg,
                :num_sets,
                :workout_id,
                :notes
            )
            RETURNING id
            """
        ),
        {
            "exercise_catalog_id": exercise_catalog_id,
            "exercise_name": exercise_name,
            "weight_used": weight_used,
            "weight_unit": weight_unit,
            "weight_used_kg": weight_used_kg,
            "num_sets": num_sets,
            "workout_id": workout_id,
            "notes": notes,
        },
    )
    return result.scalar_one()



def load_json_any(path: Path) -> Any:
    """
    Load a JSON payload.
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


def get_default_unit(conn: Connection, user_id: int, override_unit: str | None) -> str:
    if override_unit:
        unit_norm = _normalize_unit(override_unit)
        if unit_norm not in VALID_WEIGHT_UNITS:
            raise ValueError("Invalid unit override. Use 'lb' or 'kg'.")
        return unit_norm

    user = users_repo.get_user(conn, user_id)
    if user and user.get("weight_unit") in VALID_WEIGHT_UNITS:
        return user["weight_unit"]
    return DEFAULT_WEIGHT_UNIT


def exercise_signature(exercise: dict) -> tuple:
    return (
        exercise.get("notes") or "",
        exercise.get("exercise_name") or "",
        exercise.get("weight_used"),
        exercise.get("weight_unit"),
        exercise.get("num_of_sets"),
    )


def load_existing_signatures(conn: Connection, workout_id: int) -> set[tuple]:
    sql = """
        SELECT id, notes, exercise_name, weight_used, weight_unit, num_of_sets
        FROM exercise
        WHERE workout_id = :workout_id
    """
    rows = conn.execute(text(sql), {"workout_id": workout_id}).mappings().all()
    signatures: set[tuple] = set()
    for row in rows:
        signatures.add(
            (
                row["notes"] or "",
                row["exercise_name"] or "",
                row["weight_used"],
                row["weight_unit"],
                row["num_of_sets"],
            )
        )
    return signatures


def import_legacy(
    json_path: Path,
    user_id: int,
    *,
    dry_run: bool = False,
    unit: str | None = None,
    tz: str | None = None,
    strict: bool = False,
    report_path: Path | None = None,
    source: str = "auto",
    dedupe: bool = False,
) -> dict:
    """
    Import workout JSON into the new schema using a normalization step.
    """
    payload = load_json_any(json_path)

    conn = get_conn()
    trans = conn.begin()
    try:
        if tz:
            ZoneInfo(tz)
        default_unit = get_default_unit(conn, user_id, unit)
        normalized, report = normalize_payload(
            payload,
            default_unit=default_unit,
            tz=tz,
            strict=strict,
            source=source,
        )

        count_workouts_touched = 0
        count_exercises_created = 0
        count_exercises_skipped = 0
        count_exercise_names_inferred = 0
        count_exercise_names_matched = 0
        count_exercise_names_created = 0
        seen_workouts: set[str] = set()
        workout_cache: dict[str, tuple[int, set[tuple]]] = {}
        catalog_cache: dict[str, int] = {
            row["name"]: row["id"]
            for row in exercise_catalog_repo.list_all_with_details(conn, user_id)
        }

        for idx, workout in enumerate(normalized, start=1):
            date_str = workout.get("date")
            if not date_str:
                report["skipped"].append({"index": idx, "reason": "missing workout date"})
                count_exercises_skipped += len(workout.get("exercises") or [])
                continue

            if date_str not in workout_cache:
                workout_id, _created = get_or_create_workout(
                    conn,
                    user_id=user_id,
                    date=date_str,
                )
                existing_signatures = load_existing_signatures(conn, workout_id) if dedupe else set()
                workout_cache[date_str] = (workout_id, existing_signatures)

            workout_id, existing_signatures = workout_cache[date_str]

            if date_str not in seen_workouts:
                seen_workouts.add(date_str)
                count_workouts_touched += 1

            append_workout_notes(conn, workout_id, workout.get("notes"))

            for exercise in workout.get("exercises") or []:
                signature = exercise_signature(exercise)
                if dedupe and signature in existing_signatures:
                    report["skipped"].append(
                        {
                            "index": idx,
                            "reason": "duplicate exercise (dedupe)",
                            "date": date_str,
                        }
                    )
                    count_exercises_skipped += 1
                    continue

                weight_used = exercise.get("weight_used")
                weight_unit = exercise.get("weight_unit") or default_unit
                weight_used_kg = weight_to_kg(weight_used, weight_unit)
                exercise_name = exercise.get("exercise_name")
                if not exercise_name:
                    exercise_name = _normalize_exercise_name(
                        _extract_exercise_name(exercise.get("notes"))
                    )
                    if exercise_name:
                        count_exercise_names_inferred += 1

                metric_type, tags = infer_metric_type(exercise.get("muscles") or [])

                exercise_catalog_id = None
                if exercise_name:
                    existing_names = list(catalog_cache.keys())
                    match_name, match_score = _best_catalog_match(existing_names, exercise_name)
                    if match_name and match_score >= FUZZY_MATCH_THRESHOLD:
                        exercise_catalog_id = catalog_cache[match_name]
                        exercise_catalog_repo.set_metric_type(
                            conn, exercise_catalog_id, metric_type, commit=False
                        )
                        count_exercise_names_matched += 1
                    else:
                        exercise_catalog_id = exercise_catalog_repo.get_or_create(
                            conn,
                            user_id=user_id,
                            name=exercise_name,
                            metric_type=metric_type,
                            commit=False,
                        )
                        if exercise_catalog_id:
                            catalog_cache[exercise_name] = exercise_catalog_id
                            count_exercise_names_created += 1
                    if exercise_catalog_id and tags:
                        exercise_catalog_repo.set_tags(
                            conn, exercise_catalog_id, tags, commit=False
                        )

                insert_exercise(
                    conn,
                    workout_id=workout_id,
                    exercise_catalog_id=exercise_catalog_id,
                    exercise_name=exercise_name,
                    weight_used=weight_used,
                    weight_unit=weight_unit,
                    weight_used_kg=weight_used_kg,
                    num_sets=exercise.get("num_of_sets"),
                    notes=exercise.get("notes"),
                )
                count_exercises_created += 1

                if dedupe:
                    existing_signatures.add(signature)

        if dry_run:
            trans.rollback()
        else:
            trans.commit()

        result = {
            "dry_run": dry_run,
            "total_items": len(_coerce_to_list(payload)),
            "normalized_workouts": len(normalized),
            "workouts_touched": count_workouts_touched,
            "exercises_created": count_exercises_created,
            "exercises_skipped": count_exercises_skipped,
            "exercise_names_inferred": count_exercise_names_inferred,
            "exercise_names_matched": count_exercise_names_matched,
            "exercise_names_created": count_exercise_names_created,
            "warnings": len(report["warnings"]),
            "skipped": len(report["skipped"]),
        }

        if report_path:
            report_payload = {
                "summary": result,
                "warnings": report["warnings"],
                "skipped": report["skipped"],
            }
            report_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")

        result["report_path"] = str(report_path) if report_path else None
        return result
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
    parser.add_argument(
        "--unit",
        choices=["lb", "kg"],
        help="Default weight unit when missing (defaults to user's preference)",
    )
    parser.add_argument(
        "--tz",
        help="Timezone name for parsing datetimes (e.g., 'America/Los_Angeles')",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail fast on invalid values instead of skipping or warning",
    )
    parser.add_argument(
        "--report",
        help="Write a JSON import report to the given path",
    )
    parser.add_argument(
        "--source",
        choices=["auto", "legacy", "generic"],
        default="auto",
        help="Force a mapping strategy instead of auto-detect",
    )
    parser.add_argument(
        "--dedupe",
        action="store_true",
        help="Skip exercises that already exist for the workout date",
    )

    args = parser.parse_args()
    json_path = Path(args.path)

    if not json_path.exists():
        print(f"❌ File not found: {json_path}")
        sys.exit(1)

    report_path = Path(args.report) if args.report else None

    result = import_legacy(
        json_path=json_path,
        user_id=args.user_id,
        dry_run=args.dry_run,
        unit=args.unit,
        tz=args.tz,
        strict=args.strict,
        report_path=report_path,
        source=args.source,
        dedupe=args.dedupe,
    )

    mode = "DRY RUN" if args.dry_run else "IMPORT"
    print(f"\n✅ {mode} complete for {json_path}")
    for k, v in result.items():
        print(f" - {k}: {v}")


if __name__ == "__main__":
    main()
