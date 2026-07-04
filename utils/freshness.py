# utils/freshness.py
#
# Pure date-math for "what hasn't been trained in a while" -- a training
# organization aid, not a recovery/medical readiness signal. Actual muscle
# recovery depends on sleep, intensity, and individual factors a date
# subtraction can't see; this only answers "what haven't I hit lately."

from utils.body_regions import REGION_SLUGS

# Below this many effective days, nothing is considered overdue enough to
# flag -- keeps a well-balanced week (or a brand-new account with little
# history) from nagging about something that's barely behind.
OVERDUE_FLOOR_DAYS = 4


def compute_effective_days(last_trained: dict, today) -> dict[str, float | None]:
    """
    last_trained: {region_slug: {rank: date|None}} -- rank 1 is an
    exercise's primary target for that region, rank 2 secondary, and so
    on (missing slugs/ranks are treated as never trained there).

    Returns {region_slug: effective_days_since | None}. None means never
    trained at all -- callers treat that as maximally overdue.

    Rank 1 anchors the estimate. Each weaker rank only pulls freshness
    back toward "trained" if it was hit *more recently* than the current
    estimate, and by a diminishing fraction (1/rank) -- so a rank-2 hit
    pulls halfway, a rank-3 hit a third of the way, and so on. This way
    benching all week doesn't make triceps/front-delts read as neglected
    just because they were never anyone's primary target.
    """
    effective: dict[str, float | None] = {}
    for slug in REGION_SLUGS:
        ranks = last_trained.get(slug, {})
        days_by_rank = {
            rank: (today - date).days for rank, date in ranks.items() if date is not None
        }

        if not days_by_rank:
            effective[slug] = None
            continue

        sorted_ranks = sorted(days_by_rank)
        value = days_by_rank[sorted_ranks[0]]
        for rank in sorted_ranks[1:]:
            days = days_by_rank[rank]
            if days < value:
                value = value - (value - days) / rank
        effective[slug] = value
    return effective


def most_overdue_regions(effective_days: dict[str, float | None], floor_days: int = OVERDUE_FLOOR_DAYS) -> list[str]:
    """
    Region(s) tied for longest since trained, provided that's at least
    floor_days. Never-trained regions (None) are excluded from the
    comparison entirely -- "you've never done this" isn't the same signal
    as "you used to train this and let it slide", and treating it the same
    would light up most of the map for any account without deep history.
    """
    trained = {slug: days for slug, days in effective_days.items() if days is not None}
    if not trained:
        return []

    worst = max(trained.values())
    if worst < floor_days:
        return []
    return [slug for slug, days in trained.items() if days == worst]
