from datetime import date


def ordinal(n: int) -> str:
    if 11 <= n <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_date(value: date) -> str:
    return f"{value.strftime('%b')} {ordinal(value.day)}, {value.year}"
