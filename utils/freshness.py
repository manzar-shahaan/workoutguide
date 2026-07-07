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
    last_trained: {region_slug: {rank: date|None}}

    Returns {region_slug: days_since_last_trained | None}.

    Two-part rule:
      1. Gate: a region only enters overdue tracking if the user has at
         least one rank-1 (primary target) exercise for it. Muscles
         never explicitly targeted as primary stay out of suggestions.
      2. Freshness: once gated, freshness is measured from the most
         recent training date at ANY rank. Working obliques as rank-2
         yesterday should clear the overdue pulse, even if the last
         dedicated oblique session was longer ago.

    None means never trained as a primary target.
    """
    effective: dict[str, float | None] = {}
    for slug in REGION_SLUGS:
        ranks = last_trained.get(slug, {})
        if not ranks.get(1):
            effective[slug] = None
            continue
        valid_dates = [d for d in ranks.values() if d is not None]
        most_recent = max(valid_dates)
        effective[slug] = (today - most_recent).days
    return effective


def most_overdue_regions(
    effective_days: dict[str, float | None],
    floor_days: int = OVERDUE_FLOOR_DAYS,
    max_count: int = 3,
) -> list[str]:
    """
    Up to max_count most-overdue regions, sorted most-overdue first,
    provided they've been untrained for at least floor_days. Never-trained
    regions (None) are excluded -- a blank history isn't a training debt.
    """
    overdue = [
        (slug, days)
        for slug, days in effective_days.items()
        if days is not None and days >= floor_days
    ]
    if not overdue:
        return []
    overdue.sort(key=lambda x: x[1], reverse=True)
    return [slug for slug, _ in overdue[:max_count]]
