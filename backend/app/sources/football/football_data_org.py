"""football-data.org v4 connector (primary football source).

Includes manual pacing between requests and a single retry that honours the
``Retry-After`` header on HTTP 429, to stay within the free tier limits.
"""

import time

from ...services import http_client
from ..base import parse_iso_datetime


class FootballDataOrgClient:
    slug = "football_data_org"
    sport = "football"
    rank = 90

    def __init__(
        self,
        api_key: str,
        base_url: str,
        request_delay: float = 0.0,
        respect_retry_after: bool = True,
        log_callback=None,
        sleeper=None,
        requester=None,
    ):
        self._api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.request_delay = float(request_delay or 0.0)
        self.respect_retry_after = respect_retry_after
        self._log = log_callback
        self._sleep = sleeper or time.sleep
        self._request_json = requester or http_client.request_json
        self._made_request = False

    def headers(self) -> dict:
        # The token is only placed in the request header; never logged.
        return {"X-Auth-Token": self._api_key} if self._api_key else {}

    def _log_msg(self, level: str, message: str) -> None:
        if self._log:
            self._log(level, message)

    def _do(self, url: str) -> dict:
        # Pace requests: wait before every request after the first one.
        if self.request_delay > 0 and self._made_request:
            self._log_msg("info", f"waiting {self.request_delay}s before next football-data.org request")
            self._sleep(self.request_delay)
        self._made_request = True

        result = self._request_json(url, headers=self.headers())

        # One retry honouring Retry-After (or the configured delay) on 429.
        if result.get("status") == 429 and self.respect_retry_after:
            retry_after = result.get("retry_after")
            try:
                wait = float(retry_after) if retry_after else self.request_delay
            except (TypeError, ValueError):
                wait = self.request_delay
            self._log_msg("warning", f"HTTP 429 on request; waiting {wait}s before one retry")
            if wait > 0:
                self._sleep(wait)
            result = self._request_json(url, headers=self.headers())
        return result

    def get_competition_matches(self, code, date_from=None, date_to=None) -> dict:
        url = f"{self.base_url}/competitions/{code}/matches"
        params = []
        if date_from:
            params.append(f"dateFrom={date_from}")
        if date_to:
            params.append(f"dateTo={date_to}")
        if params:
            url += "?" + "&".join(params)
        return self._do(url)

    def get_matches(self, date_from, date_to, competitions=None) -> dict:
        url = f"{self.base_url}/matches?dateFrom={date_from}&dateTo={date_to}"
        if competitions:
            url += "&competitions=" + ",".join(competitions)
        return self._do(url)

    def get_competition_standings(self, code) -> dict:
        return self._do(f"{self.base_url}/competitions/{code}/standings")

    @staticmethod
    def normalize_competition(raw: dict) -> dict:
        area = raw.get("area") or {}
        return {
            "source_external_id": str(raw.get("id")),
            "code": raw.get("code"),
            "name": raw.get("name") or "?",
            "country": area.get("name"),
            "emblem_url": raw.get("emblem"),
        }

    @staticmethod
    def normalize_team(raw: dict) -> dict:
        return {
            "id": raw.get("id"),
            "name": raw.get("name"),
            "shortName": raw.get("shortName"),
            "tla": raw.get("tla"),
            "crest": raw.get("crest"),
        }

    @staticmethod
    def normalize_match(raw: dict) -> dict:
        score = raw.get("score") or {}
        full = score.get("fullTime") or {}
        half = score.get("halfTime") or {}
        return {
            "source_external_id": str(raw.get("id")),
            "start_time": parse_iso_datetime(raw.get("utcDate")),
            "status": raw.get("status"),
            "matchday": raw.get("matchday"),
            "stage": raw.get("stage"),
            "group_name": raw.get("group"),
            "home_score": full.get("home"),
            "away_score": full.get("away"),
            "ht_home_score": half.get("home"),
            "ht_away_score": half.get("away"),
            "winner": score.get("winner"),
            "home_team": raw.get("homeTeam") or {},
            "away_team": raw.get("awayTeam") or {},
        }

    @staticmethod
    def normalize_standings(standings_json: dict) -> list:
        rows = []
        season_obj = standings_json.get("season") or {}
        season = None
        if season_obj.get("startDate"):
            season = str(season_obj["startDate"])[:4]
        for block in standings_json.get("standings", []):
            if block.get("type") and block.get("type") != "TOTAL":
                continue
            for row in block.get("table", []):
                rows.append(
                    {
                        "team": row.get("team") or {},
                        "season": season,
                        "position": row.get("position"),
                        "played_games": row.get("playedGames"),
                        "won": row.get("won"),
                        "draw": row.get("draw"),
                        "lost": row.get("lost"),
                        "points": row.get("points"),
                        "goals_for": row.get("goalsFor"),
                        "goals_against": row.get("goalsAgainst"),
                        "goal_difference": row.get("goalDifference"),
                    }
                )
        return rows
