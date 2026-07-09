# utils/muscle_volume.py
#
# Distribute an exercise's training volume across its targeted muscles and
# rank muscles within a workout by descending share of that volume.
#
# Muscles are tagged on an exercise in priority order (exercise_catalog_region
# .rank: 1 = primary, 2 = secondary, ...). Each rank's share of the
# exercise's volume is half of the rank before it (primary 1x, secondary
# 0.5x, tertiary 0.25x, ...), normalized so the shares sum to the exercise's
# volume -- e.g. a pull-up's volume splits ~57% back / ~29% rear delts /
# ~14% forearms.


def _exercise_work(sets: list[dict]) -> float:
    """Total training volume for one exercise: weight_kg * reps when a
    weight was logged, else reps alone -- bodyweight movements (pull-ups,
    dips) have no loaded weight, so rep count stands in for volume."""
    total = 0.0
    for s in sets:
        reps = s.get("reps")
        if reps is None:
            continue
        weight_kg = s.get("weight_used_kg")
        total += (weight_kg * reps) if weight_kg is not None else reps
    return total


def rank_muscles_by_volume(exercises: list[dict]) -> list[str]:
    """
    exercises: [{"muscles_list": [{"name": ...}, ...] in rank order,
                 "sets": [{"weight_used_kg": ..., "reps": ...}, ...]}, ...]

    Returns muscle names sorted by descending share of total workout
    volume. Falls back to first-seen order (alphabetical, per the source
    SQL) when no exercise carries any volume, e.g. an all-cardio session.
    """
    totals: dict[str, float] = {}
    order: list[str] = []

    for ex in exercises:
        names = [m["name"] for m in ex.get("muscles_list", [])]
        for name in names:
            if name not in totals:
                totals[name] = 0.0
                order.append(name)

        if not names:
            continue

        work = _exercise_work(ex.get("sets", []))
        if work <= 0:
            continue

        weights = [0.5 ** rank for rank in range(len(names))]
        weight_sum = sum(weights)
        for name, w in zip(names, weights):
            totals[name] += work * (w / weight_sum)

    if not any(totals.values()):
        return order

    return sorted(order, key=lambda name: totals[name], reverse=True)
