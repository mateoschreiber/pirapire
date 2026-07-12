"""API-Football (api-sports.io v3) client.

Free plan aware: uses the ``season`` parameter (the ``last`` parameter is not
available on the free tier) and authenticates only with the ``x-apisports-key``
header, which is never logged. Includes manual pacing, a bounded request
counter and a single retry that honours ``Retry-After`` on HTTP 429.
"""

from __future__ import annotations

import time
from urllib.parse import urlencode

from ...services import http_client


class ApiFootballClient:
    slug = "api_football"
    sport = "football"
    rank = 88

    def __init__(
        self,
        api_key: str,
        base_url: str,
        request_delay: float = 1.0,
        cache_ttl_seconds: float = 300,
        max_requests: int = 90,
        requester=None,
        sleeper=None,
        log_callback=None,
    ):
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.request_delay = max(0.0, float(request_delay or 0.0))
        self.cache_ttl_seconds = max(0.0, float(cache_ttl_seconds))
        self.max_requests = max(0, int(max_requests))
        self._request_json = requester or http_client.request_json
        self._sleep = sleeper or time.sleep
        self._log = log_callback
        self._made_request = False
        self._cache: dict[str, tuple[float, dict]] = {}
        self.request_count = 0
        self.budget_exhausted = False

    def headers(self) -> dict:
        return {"x-apisports-key": self._api_key} if self._api_key else {}

    def _log_msg(self, level: str, message: str) -> None:
        if self._log:
            self._log(level, message)

    def _do(self, path: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        if params:
            url += "?" + urlencode(params)
        cached = self._cache.get(url)
        if cached and time.monotonic() - cached[0] < self.cache_ttl_seconds:
            return cached[1]
        if self.max_requests and self.request_count >= self.max_requests:
            self.budget_exhausted = True
            return {"ok": False, "status": None, "data": None, "error": "budget_exhausted", "retry_after": None}
        if self._made_request and self.request_delay > 0:
            self._sleep(self.request_delay)
        self._made_request = True
        self.request_count += 1
        result = self._request_json(url, headers=self.headers())
        if result.get("status") == 429:
            retry_after = result.get("retry_after")
            try:
                wait = float(retry_after) if retry_after else self.request_delay
            except (TypeError, ValueError):
                wait = self.request_delay
            self._log_msg("warning", f"API-Football HTTP 429; single retry after {wait}s")
            if wait > 0:
                self._sleep(wait)
            self.request_count += 1
            result = self._request_json(url, headers=self.headers())
        content_type = (result.get("content_type") or "").lower()
        if result.get("ok") and content_type and "json" not in content_type:
            return {"ok": False, "status": result.get("status"), "data": None, "error": "provider_invalid_content_type", "retry_after": None}
        if result.get("ok") and not isinstance(result.get("data"), dict):
            return {"ok": False, "status": result.get("status"), "data": None, "error": "provider_invalid_structure", "retry_after": None}
        if result.get("ok"):
            self._cache[url] = (time.monotonic(), result)
        return result

    def get_status(self) -> dict:
        return self._do("status")

    def get_team_fixtures(self, team_id: int, season: int) -> dict:
        return self._do("fixtures", {"team": int(team_id), "season": int(season)})

    def get_fixture_statistics(self, fixture_id: int) -> dict:
        return self._do("fixtures/statistics", {"fixture": int(fixture_id)})

    def get_fixture_events(self, fixture_id: int) -> dict:
        return self._do("fixtures/events", {"fixture": int(fixture_id)})

    def get_fixture_players(self, fixture_id: int) -> dict:
        return self._do("fixtures/players", {"fixture": int(fixture_id)})

    @staticmethod
    def response_list(result: dict) -> list:
        data = result.get("data") if result else None
        if not isinstance(data, dict):
            return []
        resp = data.get("response")
        return resp if isinstance(resp, list) else []

    @staticmethod
    def has_provider_errors(result: dict) -> bool:
        data = result.get("data") if result else None
        if not isinstance(data, dict):
            return False
        errors = data.get("errors")
        if isinstance(errors, dict):
            return bool(errors)
        if isinstance(errors, list):
            return len(errors) > 0
        return False
