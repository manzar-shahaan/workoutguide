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
    last_trained: {region_slug: {"primary": date|None, "secondary": date|None}}
    (missing slugs are treated as never trained on either role).

    Returns {region_slug: effective_days_since | None}. None means never
    trained at all -- callers treat that as maximally overdue.

    A more recent SECONDARY hit pulls freshness halfway back toward
    "trained" rather than fully resetting it, so benching all week doesn't
    make triceps/front-delts read as neglected just because they were
    never the primary target.
    """
    effective: dict[str, float | None] = {}
    for slug in REGION_SLUGS:
        roles = last_trained.get(slug, {})
        primary_date = roles.get("primary")
        secondary_date = roles.get("secondary")

        days_primary = (today - primary_date).days if primary_date else None
        days_secondary = (today - secondary_date).days if secondary_date else None

        if days_primary is None and days_secondary is None:
            effective[slug] = None
        elif days_primary is None:
            effective[slug] = days_secondary
        elif days_secondary is None:
            effective[slug] = days_primary
        elif days_secondary < days_primary:
            effective[slug] = days_primary - (days_primary - days_secondary) / 2
        else:
            effective[slug] = days_primary
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
