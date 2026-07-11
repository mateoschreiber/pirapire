"""Controlled credential tests against fixed provider endpoints."""

from __future__ import annotations

from urllib.parse import quote, urlencode

from ..config import settings
from . import http_client


def _classify(result: dict, require_api_sports_status: bool = False) -> dict:
    status = result.get("status")
    error = result.get("error")
    content_type = (result.get("content_type") or "").lower()
    if result.get("ok"):
        if content_type and "json" not in content_type:
            return {
                "ok": False,
                "status": "failed",
                "error_code": "provider_invalid_response",
            }
        if require_api_sports_status:
            data = result.get("data")
            if not isinstance(data, dict) or data.get("errors"):
                return {"ok": False, "status": "failed", "error_code": "invalid_response"}
        return {"ok": True, "status": "success", "error_code": None}
    if status == 401:
        code = "invalid_key"
    elif status == 403:
        code = "forbidden"
    elif status == 429:
        code = "quota_exceeded"
    elif error == "timeout":
        code = "timeout"
    else:
        code = "provider_unavailable"
    return {"ok": False, "status": "failed", "error_code": code}


def test_candidate(provider_slug: str, credential_name: str, value: str) -> dict:
    value = value.strip() if isinstance(value, str) else ""
    if credential_name != "api_key" or not value:
        return {"ok": False, "status": "failed", "error_code": "invalid_candidate"}
    if provider_slug == "football_data_org":
        result = http_client.request_json(
            f"{settings.football_data_base_url.rstrip('/')}/competitions/WC",
            headers={"X-Auth-Token": value},
        )
    elif provider_slug == "api_football":
        result = http_client.request_json(
            f"{settings.api_football_base_url.rstrip('/')}/status",
            headers={"x-apisports-key": value},
        )
        return _classify(result, require_api_sports_status=True)
    elif provider_slug == "riot_api":
        result = http_client.request_json(
            "https://na1.api.riotgames.com/lol/status/v4/platform-data",
            headers={"X-Riot-Token": value},
        )
    elif provider_slug == "thesportsdb":
        query = urlencode({"t": "Arsenal"})
        result = http_client.request_json(
            "https://www.thesportsdb.com/api/v1/json/"
            f"{quote(value, safe='')}/searchteams.php?{query}"
        )
    else:
        return {"ok": False, "status": "failed", "error_code": "provider_not_testable"}
    return _classify(result)
