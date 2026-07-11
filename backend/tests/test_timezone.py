from datetime import UTC, datetime, timedelta

from app.config import settings
from app.utils import datetime_utils
from app.services.aposta_html_parser import _parse_aposta_datetime


def test_app_timezone_is_asuncion():
    assert settings.app_timezone == "America/Asuncion"


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


def test_tomorrow_across_2359_py_is_resolved_locally_then_converted_once():
    ref = datetime(2026, 7, 10, 23, 59, tzinfo=datetime_utils.get_tz())
    parsed = _parse_aposta_datetime("Mañana", "00:01", ref)
    assert parsed == datetime(2026, 7, 11, 3, 1, tzinfo=UTC)


def test_today_at_0001_py_is_resolved_on_the_local_date():
    ref = datetime(2026, 7, 11, 0, 1, tzinfo=datetime_utils.get_tz())
    parsed = _parse_aposta_datetime("Hoy", "00:01", ref)
    assert parsed == datetime(2026, 7, 11, 3, 1, tzinfo=UTC)


def test_kambi_0800_utc_displays_as_0500_py():
    display = datetime_utils.event_time_display(
        "2026-07-11T08:00:00+00:00", "confirmed_source_utc"
    )
    assert display == "11/07 05:00 PY"


def test_unconfirmed_time_is_not_labeled_py():
    display = datetime_utils.event_time_display(
        "2026-07-11T08:00:00+00:00", "unconfirmed"
    )
    assert display == "Horario pendiente de reconfirmación"
