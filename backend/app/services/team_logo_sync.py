"""Local cache for official team logos published by LoL Esports."""

import html
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import unquote

import requests


OFFICIAL_PAGES = (
    "https://lolesports.com/en-US/tournament/115548106590082745/overview",
    "https://lolesports.com/en-US/tournament/115615907996665826/overview",
    "https://lolesports.com/en-US/tournament/115548681802226458/overview",
    "https://lolesports.com/en-US/tournament/115565518151768348/overview",
    "https://lolesports.com/en-US/tournament/115570728597462574/overview",
    "https://lolesports.com/en-US/leagues/first_stand",
    "https://lolesports.com/en-US/leagues/lck",
    "https://lolesports.com/en-US/leagues/lpl",
    "https://lolesports.com/en-US/leagues/lec",
    "https://lolesports.com/en-US/leagues/lcs",
    "https://lolesports.com/en-US/leagues/cblol",
    "https://lolesports.com/en-US/leagues/lcp",
)
OUT = Path(__file__).resolve().parents[1] / "static" / "team-logos"
_ENTRY = re.compile(r'alt="([^"]+)"[^>]+src="[^"]*f=(http[^"&]+)', re.S)
_HEADERS = {"User-Agent": "PirapireLocal/1.0"}

# Schedule and historical providers use several names for the same team. Keep
# these aliases in the local manifest so rendered professional teams retain the
# official asset already downloaded from LoL Esports.
DISPLAY_ALIASES = {
    "cloud9": "cloud9-kia",
    "ag-al": "anyone-s-legend",
    "deep-cross-gaming": "relove-deep-cross-gaming",
    "gen-g": "gen-g-esports",
    "jd-gaming": "beijing-jdg-esports",
    "lng-esports": "suzhou-lng-esports",
    "ls": "los",
    "mibr-los": "mibr",
    "ninjas-in-pyjamas": "shenzhen-ninjas-in-pyjamas",
    "nongshim-redforce": "nongshim-red-force",
    "red-canids": "red-kalunga",
    "pain-legends": "pain-gaming",
    "team-liquid": "team-liquid-alienware",
    "team-secret": "team-secret-whales",
    "team-we": "xi-an-team-we",
    "thundertalk-gaming": "thunder-talk-gaming",
    "weibo-gaming": "weibogaming",
}
OFFICIAL_TEAM_ASSETS = {
    "cnb-legends": "https://storage.googleapis.com/gpt-engineer-file-uploads/l3cZJ9dCMeSnX2jCzfwDKyrIrW82/social-images/social-1777295783244-Logo-great-p.webp",
    "mibr": "https://mibr.gg/wp-content/uploads/2026/02/mibrlogo-dark.webp",
}


def team_logo_key(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"(^-|-$)", "", re.sub(r"[^a-z0-9]+", "-", normalized))


def _entries(page: str):
    response = requests.get(page, timeout=30, headers=_HEADERS)
    response.raise_for_status()
    for name, encoded_url in _ENTRY.findall(response.text):
        yield html.unescape(name), unquote(html.unescape(encoded_url)).replace("http://", "https://")


def apply_display_aliases(manifest: dict) -> None:
    """Map provider spelling variants to an already cached official logo."""
    for alias, official_key in DISPLAY_ALIASES.items():
        filename = manifest.get(official_key)
        if filename:
            manifest[alias] = filename


def sync_known_official_assets(manifest: dict) -> int:
    """Cache assets published by a team when it is not in Riot's current feed."""
    downloaded = 0
    for key, url in OFFICIAL_TEAM_ASSETS.items():
        if key in manifest:
            continue
        try:
            asset = requests.get(url, timeout=30, headers=_HEADERS)
            asset.raise_for_status()
            suffix = Path(url.split("?", 1)[0]).suffix.lower() or ".png"
            filename = f"{key}{suffix}"
            (OUT / filename).write_bytes(asset.content)
            manifest[key] = filename
            downloaded += 1
        except requests.RequestException:
            continue
    return downloaded


def sync_official_team_logos() -> dict:
    """Refresh the local cache from official Riot LoL Esports pages."""
    OUT.mkdir(parents=True, exist_ok=True)
    manifest_path = OUT / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        manifest = {}
    downloaded = sync_known_official_assets(manifest)
    apply_display_aliases(manifest)
    for page in OFFICIAL_PAGES:
        try:
            entries = _entries(page)
            for name, url in entries:
                key = team_logo_key(name)
                if not key or key in manifest:
                    continue
                suffix = Path(url.split("?", 1)[0]).suffix.lower()
                suffix = suffix if suffix in {".png", ".webp", ".jpg", ".jpeg", ".svg"} else ".png"
                filename = f"{key}{suffix}"
                try:
                    asset = requests.get(url, timeout=30, headers=_HEADERS)
                    asset.raise_for_status()
                    (OUT / filename).write_bytes(asset.content)
                    manifest[key] = filename
                    downloaded += 1
                except requests.RequestException:
                    continue
        except requests.RequestException:
            continue
    apply_display_aliases(manifest)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    return {"downloaded": downloaded, "total": len(manifest)}
