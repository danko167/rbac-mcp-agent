from __future__ import annotations

from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


def now_in_app_tz() -> datetime:
    """
    Current datetime in the application's configured timezone.
    Falls back to UTC if the timezone is invalid/unavailable.
    """
    tz_name = get_settings().app_timezone
    try:
        return datetime.now(ZoneInfo(tz_name))
    except Exception:
        return datetime.now(timezone.utc)


def today_in_app_tz() -> date:
    """Today's date in the application's configured timezone."""
    return now_in_app_tz().date()
