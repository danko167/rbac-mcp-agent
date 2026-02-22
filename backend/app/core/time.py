from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo

from app.core.config import get_settings


_timezone_ctx: ContextVar[str | None] = ContextVar("timezone_ctx", default=None)


def detect_server_timezone_name() -> str:
    """
    Detect the server host timezone as an IANA zone when possible.
    Falls back to APP_TIMEZONE and then UTC.
    """
    local_tz = datetime.now().astimezone().tzinfo
    tz_key = getattr(local_tz, "key", None)
    if isinstance(tz_key, str) and tz_key.strip():
        return normalize_timezone_name(tz_key)

    tz_name = datetime.now().astimezone().tzname()
    if isinstance(tz_name, str) and tz_name.strip():
        try:
            ZoneInfo(tz_name)
            return normalize_timezone_name(tz_name)
        except Exception:
            pass

    return normalize_timezone_name(get_settings().app_timezone)


def normalize_timezone_name(tz_name: str | None) -> str:
    """
    Validate and normalize an IANA timezone name.
    Falls back to UTC when missing/invalid.
    """
    candidate = (tz_name or "").strip()
    if not candidate:
        return "UTC"
    try:
        ZoneInfo(candidate)
    except Exception:
        return "UTC"
    return candidate


def set_current_timezone(tz_name: str | None) -> str:
    """
    Set timezone for the current execution context.
    Returns the normalized timezone that was applied.
    """
    normalized = normalize_timezone_name(tz_name)
    _timezone_ctx.set(normalized)
    return normalized


@contextmanager
def timezone_context(tz_name: str | None):
    """Temporarily set timezone for the current execution context."""
    normalized = normalize_timezone_name(tz_name)
    token = _timezone_ctx.set(normalized)
    try:
        yield normalized
    finally:
        _timezone_ctx.reset(token)


def current_timezone_name() -> str:
    """
    Resolve effective timezone for current execution context.
    Priority:
    1) context timezone set per request/tool-call
    2) APP_TIMEZONE setting
    3) UTC
    """
    tz_name = _timezone_ctx.get()
    if tz_name:
        return normalize_timezone_name(tz_name)

    return detect_server_timezone_name()


def current_tzinfo() -> ZoneInfo:
    """Effective ZoneInfo for current execution context."""
    return ZoneInfo(current_timezone_name())


def now_in_app_tz() -> datetime:
    """
    Current datetime in the application's configured timezone.
    Falls back to UTC if the timezone is invalid/unavailable.
    """
    try:
        return datetime.now(current_tzinfo())
    except Exception:
        return datetime.now(timezone.utc)


def today_in_app_tz() -> date:
    """Today's date in the application's configured timezone."""
    return now_in_app_tz().date()


def effective_user_timezone(user_timezone: str | None) -> str:
    tz_name = (user_timezone or "").strip()
    if not tz_name:
        return detect_server_timezone_name()
    return normalize_timezone_name(tz_name)
