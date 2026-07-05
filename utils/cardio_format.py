"""Display formatting for cardio duration/distance/pace -- shared by the
workout detail page and search results so both render identically."""


def format_duration(seconds) -> str | None:
    if seconds is None:
        return None
    total = round(seconds)
    hh, rem = divmod(total, 3600)
    mm, ss = divmod(rem, 60)
    if hh:
        return f"{hh}:{mm:02d}:{ss:02d}"
    return f"{mm}:{ss:02d}"


def format_distance(distance, unit) -> str | None:
    if distance is None:
        return None
    label = f" {unit}" if unit else ""
    return f"{distance:.2f}{label}"


def format_pace(seconds, distance, unit) -> str | None:
    if not seconds or not distance:
        return None
    pace_seconds = seconds / distance
    label = f"/{unit}" if unit else ""
    return f"{format_duration(pace_seconds)}{label}"
