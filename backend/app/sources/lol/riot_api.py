"""Allowlisted Riot API client for confirmed identities and match references."""

from __future__ import annotations

import time
from urllib.parse import quote, urlencode

from ...services import http_client

PLATFORMS = {
    "br1", "eun1", "euw1", "jp1", "kr", "la1", "la2", "na1", "oc1", "ph2",
    "ru", "sg2", "th2", "tr1", "tw2", "vn2",
}
REGIONS = {"americas", "asia", "europe", "sea"}


class RiotAPIClient:
    slug = "riot_api"
    sport = "lol"
    rank = 80

    def __init__(
        self,
        api_key: str,
        platform: str = "la2",
        region: str = "americas",
        request_delay: float = 1.25,
        cache_ttl_seconds: float = 300,
        requester=None,
        sleeper=None,
        log_callback=None,
    ):
        if platform not in PLATFORMS or region not in REGIONS:
            raise ValueError("invalid_riot_route")
        self._api_key = api_key
        self.platform = platform
        self.region = region
        self.request_delay = max(0.0, float(request_delay))
        self.cache_ttl_seconds = max(0.0, float(cache_ttl_seconds))
        self._request_json = requester or http_client.request_json
        self._sleep = sleeper or time.sleep
        self._log = log_callback
        self._made_request = False
        self._cache: dict[str, tuple[float, dict]] = {}
        self.request_count = 0
        self.last_rate_limit: dict = {}

    def __repr__(self) -> str:
        return f"RiotAPIClient(platform={self.platform!r}, region={self.region!r})"

    def headers(self) -> dict:
        return {"X-Riot-Token": self._api_key} if self._api_key else {}

    def _do(self, route: str, path: str, params: dict | None = None) -> dict:
        if route == "platform":
            host = f"https://{self.platform}.api.riotgames.com"
        elif route == "regional":
            host = f"https://{self.region}.api.riotgames.com"
        else:
            raise ValueError("invalid_riot_route_type")
        url = host + path
        if params:
            url += "?" + urlencode(params)
        cached = self._cache.get(url)
        if cached and time.monotonic() - cached[0] < self.cache_ttl_seconds:
            return cached[1]
        if self._made_request and self.request_delay:
            self._sleep(self.request_delay)
        self._made_request = True
        self.request_count += 1
        result = self._request_json(url, headers=self.headers())
        self.last_rate_limit = result.get("rate_limit") or {}
        if result.get("status") == 429:
            try:
                wait = max(self.request_delay, float(result.get("retry_after") or 0))
            except (TypeError, ValueError):
                wait = self.request_delay
            if self._log:
                self._log("warning", f"Riot rate-limit pause {wait}s")
            self._sleep(wait)
            self.request_count += 1
            result = self._request_json(url, headers=self.headers())
        content_type = (result.get("content_type") or "").lower()
        if result.get("ok") and content_type and "json" not in content_type:
            result = {
                "ok": False,
                "status": result.get("status"),
                "data": None,
                "error": "provider_invalid_content_type",
                "retry_after": None,
            }
        if result.get("ok") and not isinstance(result.get("data"), (dict, list)):
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

    def get_platform_status(self) -> dict:
        return self._do("platform", "/lol/status/v4/platform-data")

    def account_by_riot_id(self, game_name: str, tag_line: str) -> dict:
        game = quote(game_name, safe="")
        tag = quote(tag_line, safe="")
        return self._do("regional", f"/riot/account/v1/accounts/by-riot-id/{game}/{tag}")

    def summoner_by_puuid(self, puuid: str) -> dict:
        return self._do("platform", f"/lol/summoner/v4/summoners/by-puuid/{quote(puuid, safe='')}")

    def match_ids_by_puuid(self, puuid: str, count: int = 5) -> dict:
        return self._do(
            "regional",
            f"/lol/match/v5/matches/by-puuid/{quote(puuid, safe='')}/ids",
            {"start": 0, "count": max(1, min(int(count), 20))},
        )

    def match_by_id(self, match_id: str) -> dict:
        return self._do(
            "regional", f"/lol/match/v5/matches/{quote(match_id, safe='')}"
        )
