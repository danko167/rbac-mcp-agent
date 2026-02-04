from __future__ import annotations
import re
from datetime import date, timedelta

from app.core.time import today_in_app_tz

WEEKDAY = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _end_of_next_week(today: date) -> date:
    """
    Get the date of the end of next week (Sunday) based on today's date.
    """
    days_until_next_monday = 7 - today.weekday()
    next_monday = today + timedelta(days=days_until_next_monday)
    return next_monday + timedelta(days=6)


def _next_weekday(today: date, target_wd: int, *, force_next_week: bool) -> date:
    """
    Get the date of the next specified weekday.
    If force_next_week is True, ensure the date is at least one week ahead.
    """
    delta = (target_wd - today.weekday()) % 7
    if delta == 0:
        delta = 7
    d = today + timedelta(days=delta)

    if force_next_week and (d - today).days < 7:
        d += timedelta(days=7)
    return d


def resolve_due_on(due_on: str | None) -> date | None:
    """
    Resolve a due date string into a date object.
    Supported formats:
    - "today"
    - "tomorrow"
    - "next week"
    - "this <weekday>" (e.g., "this monday")
    - "next <weekday>" (e.g., "next friday")
    - ISO format date (e.g., "2024-12-31")
    """
    if not due_on:
        return None

    s = due_on.strip().lower()
    today = today_in_app_tz()

    if s == "today":
        return today
    if s == "tomorrow":
        return today + timedelta(days=1)

    if s in {"next week", "nextweek"}:
        return _end_of_next_week(today)

    m = re.fullmatch(
        r"(this|next)?\s*(monday|tuesday|wednesday|thursday|friday|saturday|sunday)",
        s,
    )
    if m:
        which = m.group(1)
        wd_name = m.group(2)
        target = WEEKDAY[wd_name]

        if which == "next":
            return _next_weekday(today, target, force_next_week=True)

        return _next_weekday(today, target, force_next_week=False)

    return date.fromisoformat(s)
