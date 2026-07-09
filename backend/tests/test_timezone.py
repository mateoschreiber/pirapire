from datetime import UTC, datetime, timedelta

from app.config import settings
from app.utils import datetime_utils


def test_app_timezone_is_buenos_aires():
    assert settings.app_timezone == "America/Argentina/Buenos_Aires"


def test_to_local_applies_minus_three_offset():
    dt = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)
    local = datetime_utils.to_local(dt)
    assert local.utcoffset() == timedelta(hours=-3)


def test_offset_str():
    assert datetime_utils.offset_str() == "-03:00"


def test_format_local_naive_treated_as_utc():
    dt = datetime(2026, 1, 15, 12, 0)
    out = datetime_utils.format_local(dt, "%H:%M")
    assert out == "09:00"
