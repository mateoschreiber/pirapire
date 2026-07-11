"""Strict TheSportsDB free-v1 client for metadata fallback only."""

from __future__ import annotations

import time
from urllib.parse import quote, urlencode

from ...services import http_client


class TheSportsDBClient:
    slug = "thesportsdb"
    sport = "football"
    rank = 70
    base_url = "https://www.thesportsdb.com/api/v1/json"
    _ENDPOINTS = {
        "searchteams.php",
        "lookupteam.php",
        "lookupplayer.php",
        "lookup_all_players.php",
        "lookupevent.php",
        "lookupeventstats.php",
        "lookuplineup.php",
    }

    def __init__(
        self,
        api_key: str,
        request_delay: float = 2.0,
        cache_ttl_seconds: float = 900,
        requester=None,
        sleeper=None,
        log_callback=None,
    ):
        self._api_key = api_key
        self.request_delay = max(2.0, float(request_delay or 0.0))
        self.cache_ttl_seconds = max(0.0, float(cache_ttl_seconds))
        self._request_json = requester or http_client.request_json
        self._sleep = sleeper or time.sleep
        self._log = log_callback
        self._made_request = False
        self._cache: dict[str, tuple[float, dict]] = {}
        self.request_count = 0

    def __repr__(self) -> str:
        return "TheSportsDBClient(mode='free-v1')"

    def _do(self, endpoint: str, params: dict[str, object]) -> dict:
        if endpoint not in self._ENDPOINTS:
            raise ValueError("unsupported_thesportsdb_endpoint")
        query = urlencode(params)
        key = quote(self._api_key, safe="")
        url = f"{self.base_url}/{key}/{endpoint}?{query}"
        cached = self._cache.get(url)
        if cached and time.monotonic() - cached[0] < self.cache_ttl_seconds:
            return cached[1]
        if self._made_request:
            self._sleep(self.request_delay)
        self._made_request = True
        self.request_count += 1
        result = self._request_json(url)
        if result.get("status") == 429:
            try:
                wait = max(self.request_delay, float(result.get("retry_after") or 0))
            except (TypeError, ValueError):
                wait = self.request_delay
            if self._log:
                self._log("warning", f"TheSportsDB quota pause {wait}s")
            self._sleep(wait)
            self.request_count += 1
            result = self._request_json(url)
        content_type = (result.get("content_type") or "").lower()
        if result.get("ok") and content_type and "json" not in content_type:
            result = {
                "ok": False,
                "status": result.get("status"),
                "data": None,
                "error": "provider_invalid_content_type",
                "retry_after": None,
            }
        if result.get("ok") and not isinstance(result.get("data"), dict):
            result = {
                "ok": False,
                "status": result.get("status"),
                "data": None,
                "error": "provider_invalid_structure",
                "retry_after": None,
            }
        if result.get("ok"):
            self._cache[url] = (time.monotonic(), result)
        return result

    def search_teams(self, name: str) -> dict:
        return self._do("searchteams.php", {"t": name})

    def lookup_team(self, external_id: str) -> dict:
        return self._do("lookupteam.php", {"id": external_id})

    def lookup_player(self, external_id: str) -> dict:
        return self._do("lookupplayer.php", {"id": external_id})

    def lookup_all_players(self, team_external_id: str) -> dict:
        return self._do("lookup_all_players.php", {"id": team_external_id})

    def lookup_event(self, external_id: str) -> dict:
        return self._do("lookupevent.php", {"id": external_id})

    def lookup_event_stats(self, external_id: str) -> dict:
        return self._do("lookupeventstats.php", {"id": external_id})

    def lookup_lineup(self, external_id: str) -> dict:
        return self._do("lookuplineup.php", {"id": external_id})
