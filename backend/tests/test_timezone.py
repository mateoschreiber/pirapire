from datetime import UTC, datetime, timedelta
from app.config import settings
from app.utils import datetime_utils


def test_app_timezone_is_asuncion():
    assert settings.app_timezone == "America/Asuncion"


def test_to_local_applies_minus_three_offset():
    local = datetime_utils.to_local(datetime(2026, 1, 15, 12, 0, tzinfo=UTC))
    assert local.utcoffset() == timedelta(hours=-3)


def test_offset_and_format():
    assert datetime_utils.offset_str() == "-03:00"
    assert datetime_utils.format_local(datetime(2026, 1, 15, 12, 0), "%H:%M") == "09:00"