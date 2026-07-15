"""Timezone helpers: store UTC internally, display in APP_TIMEZONE."""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..config import settings


def get_tz() -> ZoneInfo:
    try:
        return ZoneInfo(settings.app_timezone)
    except (ZoneInfoNotFoundError, ValueError, KeyError):
        return ZoneInfo("UTC")


def to_local(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.astimezone(get_tz())


def format_local(dt: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    local = to_local(dt)
    return local.strftime(fmt) if local else ""


def now_local() -> datetime:
    return datetime.now(get_tz())


def offset_str() -> str:
    """Current UTC offset for APP_TIMEZONE, e.g. '-03:00'."""
    off = now_local().strftime("%z")
    return f"{off[:3]}:{off[3:]}" if off else ""
