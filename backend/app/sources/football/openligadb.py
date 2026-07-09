"""OpenLigaDB connector (football fallback source)."""

from ...services import http_client
from ..base import parse_iso_datetime


class OpenLigaDBClient:
    slug = "openligadb"
    sport = "football"
    rank = 85

    def __init__(self, base_url: str = "https://api.openligadb.de"):
        self.base_url = base_url.rstrip("/")

    def get_matches_by_league_season(self, shortcut, season) -> dict:
        url = f"{self.base_url}/getmatchdata/{shortcut}/{season}"
        return http_client.request_json(url)

    def get_next_matches(self, shortcut) -> dict:
        url = f"{self.base_url}/getnextmatchbyleagueshortcut/{shortcut}"
        return http_client.request_json(url)

    def get_last_matches(self, shortcut) -> dict:
        url = f"{self.base_url}/getlastmatchbyleagueshortcut/{shortcut}"
        return http_client.request_json(url)

    @staticmethod
    def normalize_match(raw: dict) -> dict:
        results = raw.get("matchResults") or []
        full = next((r for r in results if r.get("resultTypeID") == 2), None)
        if full is None and results:
            full = results[-1]
        half = next((r for r in results if r.get("resultTypeID") == 1), None) or {}
        full = full or {}
        team1 = raw.get("team1") or {}
        team2 = raw.get("team2") or {}
        group = raw.get("group") or {}
        return {
            "source_external_id": str(raw.get("matchID")),
            "start_time": parse_iso_datetime(raw.get("matchDateTimeUTC")),
            "status": "FINISHED" if raw.get("matchIsFinished") else "SCHEDULED",
            "matchday": group.get("groupOrderID"),
            "stage": None,
            "group_name": group.get("groupName"),
            "home_score": full.get("pointsTeam1"),
            "away_score": full.get("pointsTeam2"),
            "ht_home_score": half.get("pointsTeam1") if half else None,
            "ht_away_score": half.get("pointsTeam2") if half else None,
            "winner": None,
            "home_team": {
                "id": team1.get("teamId"),
                "name": team1.get("teamName"),
                "shortName": team1.get("shortName"),
                "tla": None,
                "crest": team1.get("teamIconUrl"),
            },
            "away_team": {
                "id": team2.get("teamId"),
                "name": team2.get("teamName"),
                "shortName": team2.get("shortName"),
                "tla": None,
                "crest": team2.get("teamIconUrl"),
            },
        }
