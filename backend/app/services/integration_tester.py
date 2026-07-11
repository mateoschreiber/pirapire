"""Controlled credential tests against fixed provider endpoints."""

from __future__ import annotations

from ..config import settings
from . import http_client


def _classify(result: dict) -> dict:
    status = result.get("status")
    error = result.get("error")
    if result.get("ok"):
        return {"ok": True, "status": "success", "error_code": None}
    if status in (401, 403):
        code = "invalid_credential"
    elif status == 429:
        code = "rate_limited"
    elif error == "timeout":
        code = "timeout"
    else:
        code = "provider_unavailable"
    return {"ok": False, "status": "failed", "error_code": code}


def test_candidate(provider_slug: str, credential_name: str, value: str) -> dict:
    if credential_name != "api_key" or not value:
        return {"ok": False, "status": "failed", "error_code": "invalid_candidate"}
    if provider_slug == "football_data_org":
        result = http_client.request_json(
            f"{settings.football_data_base_url.rstrip('/')}/competitions/WC",
            headers={"X-Auth-Token": value},
        )
    elif provider_slug == "riot_api":
        result = http_client.request_json(
            "https://na1.api.riotgames.com/lol/status/v4/platform-data",
            headers={"X-Riot-Token": value},
        )
    elif provider_slug == "thesportsdb":
        result = http_client.request_json(
            f"https://www.thesportsdb.com/api/v1/json/{value}/searchteams.php?t=Arsenal"
        )
    else:
        return {"ok": False, "status": "failed", "error_code": "provider_not_testable"}
    return _classify(result)
