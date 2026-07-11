import json
import ssl

import pytest

from app.routers.events import _can_calculate_no_vig
from app.services import kambi_lol_connector


class _Response:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps({"ok": True}).encode()


def test_kambi_uses_default_verified_tls_context(monkeypatch):
    seen = {}

    def fake_urlopen(request, timeout, context):
        seen["timeout"] = timeout
        seen["context"] = context
        return _Response()

    monkeypatch.setattr(kambi_lol_connector.urllib.request, "urlopen", fake_urlopen)
    assert kambi_lol_connector._fetch_json(
        "https://example.test", timeout=7, retries=0
    ) == {"ok": True}
    assert seen["timeout"] == 7
    assert seen["context"].check_hostname is True
    assert seen["context"].verify_mode == ssl.CERT_REQUIRED


def test_kambi_rejects_invalid_certificate_without_retry(monkeypatch):
    calls = {"count": 0}

    def invalid_certificate(*args, **kwargs):
        calls["count"] += 1
        raise ssl.SSLCertVerificationError("certificate verify failed")

    monkeypatch.setattr(
        kambi_lol_connector.urllib.request, "urlopen", invalid_certificate
    )
    with pytest.raises(ssl.SSLCertVerificationError):
        kambi_lol_connector._fetch_json("https://invalid.test", retries=3)
    assert calls["count"] == 1


def test_lol_no_vig_is_disabled_even_for_two_outcomes():
    assert _can_calculate_no_vig("lol", "map_winner", 2) is False


def test_football_no_vig_requires_exact_complete_market():
    assert _can_calculate_no_vig("football", "match_winner", 3) is True
    assert _can_calculate_no_vig("football", "match_winner", 4) is False
    assert _can_calculate_no_vig("football", "total_goals_over_under", 2) is True
    assert _can_calculate_no_vig("football", "total_goals_over_under", 3) is False
