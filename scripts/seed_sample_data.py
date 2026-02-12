#!/usr/bin/env python3
from __future__ import annotations

import argparse
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import text

# Ensure project root is importable when running this script directly
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.db.connection import get_conn
from app.db.repositories import workouts as workouts_repo
from app.db.repositories import exercises as exercises_repo
from app.db.repositories import muscles as muscles_repo


def _normalize_weight_to_kg(weight_used: float | None, weight_unit: str | None) -> float | None:
    if weight_used is None:
        return None
    if weight_unit == "kg":
        return float(weight_used)
    if weight_unit == "lb":
        return float(weight_used) * 0.45359237
    return None


def _find_user_id(conn, user_id: int | None, email: str | None) -> int | None:
    if user_id is not None:
        result = conn.execute(
            text("SELECT id FROM app_user WHERE id = :id"),
            {"id": user_id},
        ).mappings().fetchone()
        return result["id"] if result else None

    if email:
        result = conn.execute(
            text("SELECT id FROM app_user WHERE email = :email"),
            {"email": email.lower()},
        ).mappings().fetchone()
        return result["id"] if result else None

    result = conn.execute(
        text("SELECT id FROM app_user ORDER BY id LIMIT 1")
    ).mappings().fetchone()
    return result["id"] if result else None


def seed_sample_data(user_id: int, seed: int = 7) -> None:
    today = date.today()
    random.seed(seed)

    # Choose ~7 workout days within the last 90 days -> ~21 exercises total.
    days = set()
    while len(days) < 7:
        offset = random.randint(0, 90)
        days.add(today - timedelta(days=offset))
    workout_days = sorted(days)

    conn = get_conn()
    try:
        muscles_repo.ensure_default_muscles(conn, user_id)
        muscles = muscles_repo.list_muscles(conn, user_id=user_id, active_only=True)
        muscle_map = {m["name"]: m["id"] for m in muscles}

        templates = [
            {"notes": "bench press", "muscle": "chest", "base": 135, "step": 2.5, "sets": 4},
            {"notes": "deadlift", "muscle": "back", "base": 185, "step": 5, "sets": 3},
            {"notes": "squat", "muscle": "legs", "base": 155, "step": 5, "sets": 4},
            {"notes": "bicep curls", "muscle": "arms", "base": 25, "step": 2.5, "sets": 3},
            {"notes": "weighted crunches", "muscle": "abs", "base": 10, "step": 2.5, "sets": 3},
        ]
        cardio_templates = [
            {"notes": "treadmill run (20 min)", "muscle": "cardio"},
            {"notes": "bike ride (30 min)", "muscle": "cardio"},
        ]

        for idx, workout_day in enumerate(workout_days):
            workout = workouts_repo.get_or_create_workout_by_date(
                conn,
                user_id=user_id,
                date=workout_day.isoformat(),
            )
            workout_id = workout["id"]

            strength_choices = [
                templates[idx % len(templates)],
                templates[(idx + 2) % len(templates)],
            ]
            cardio_choice = cardio_templates[idx % len(cardio_templates)]
            day_exercises = strength_choices + [cardio_choice]

            for ex in day_exercises:
                muscle_id = muscle_map.get(ex["muscle"])
                weight_used = None
                weight_unit = "lb"
                num_of_sets = None
                avg_reps = None
                max_reps = None

                if "base" in ex:
                    weight_used = ex["base"] + (idx * ex["step"])
                    num_of_sets = ex["sets"]
                    avg_reps = random.choice([6, 8, 10, 12])
                    max_reps = avg_reps + random.choice([0, 1, 2])

                weight_used_kg = _normalize_weight_to_kg(weight_used, weight_unit)

                exercises_repo.create_exercise(
                    conn,
                    workout_id=workout_id,
                    notes=ex["notes"],
                    weight_used=weight_used,
                    weight_unit=weight_unit,
                    weight_used_kg=weight_used_kg,
                    num_of_sets=num_of_sets,
                    avg_reps=avg_reps,
                    max_reps=max_reps,
                    muscle_id=muscle_id,
                )
    finally:
        conn.close()

    print(f"Seeded sample workouts/exercises for user_id={user_id}.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Seed sample workouts/exercises for the last 3 months."
    )
    parser.add_argument("--user-id", type=int, help="Target user id")
    parser.add_argument("--email", type=str, help="Target user email")
    parser.add_argument("--seed", type=int, default=7, help="Random seed")
    args = parser.parse_args()

    conn = get_conn()
    try:
        user_id = _find_user_id(conn, args.user_id, args.email)
    finally:
        conn.close()

    if user_id is None:
        raise SystemExit("No user found. Create an account first or pass --user-id/--email.")

    seed_sample_data(user_id, seed=args.seed)


if __name__ == "__main__":
    main()
