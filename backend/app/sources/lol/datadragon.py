"""Riot Data Dragon connector (LoL static data: versions, champions)."""

from ...services import http_client


class RiotDataDragonClient:
    slug = "riot_datadragon"
    sport = "lol"
    rank = 100

    def __init__(
        self,
        base_url: str = "https://ddragon.leagueoflegends.com",
        locale: str = "es_MX",
    ):
        self.base_url = base_url.rstrip("/")
        self.locale = locale

    def get_versions(self) -> dict:
        return http_client.request_json(f"{self.base_url}/api/versions.json")

    def get_champions(self, version, locale=None) -> dict:
        loc = locale or self.locale
        url = f"{self.base_url}/cdn/{version}/data/{loc}/champion.json"
        return http_client.request_json(url)

    @staticmethod
    def latest_version(versions) -> str | None:
        if isinstance(versions, list) and versions:
            return versions[0]
        return None

    @staticmethod
    def normalize_champions(champion_json: dict, version: str) -> list:
        out = []
        for key, champ in (champion_json.get("data") or {}).items():
            out.append(
                {
                    "champion_id": champ.get("id") or key,
                    "champion_key": champ.get("key"),
                    "name": champ.get("name") or key,
                    "title": champ.get("title"),
                    "version": version,
                }
            )
        return out
