"""In-code registry of external data sources, ranking and capabilities.

This is the source of truth used to (a) seed the DataSource/SourceCapability
tables and (b) resolve which source to use for a given sport + data_type.
Nothing here performs network access; it only describes the sources.
"""

FOOTBALL_SOURCES = [
    {
        "name": "football-data.org",
        "slug": "football_data_org",
        "sport": "football",
        "rank": 90,
        "enabled_by_default": False,
        "requires_env": "FOOTBALL_DATA_API_KEY",
        "base_url": "https://api.football-data.org/v4",
        "description": "API oficial de fixtures/resultados/standings (v4).",
        "reliability_notes": "Free API key cifrada; pacing máximo 10 requests/minuto.",
        "use_for": ["fixtures", "results", "standings", "teams", "squads", "players", "half_time_score"],
        "supports_live": True,
        "supports_history": True,
        "supports_manual_import": False,
    },
    {
        "name": "OpenLigaDB",
        "slug": "openligadb",
        "sport": "football",
        "rank": 85,
        "enabled_by_default": True,
        "requires_env": None,
        "base_url": "https://api.openligadb.de",
        "description": "Fuente abierta con Swagger publico.",
        "reliability_notes": "Fuente primaria si no hay FOOTBALL_DATA_API_KEY.",
        "use_for": ["fixtures", "results", "teams", "basic_scores"],
        "supports_live": False,
        "supports_history": True,
        "supports_manual_import": False,
    },
    {
        "name": "TheSportsDB",
        "slug": "thesportsdb",
        "sport": "football",
        "rank": 70,
        "enabled_by_default": True,
        "requires_env": None,
        "base_url": "https://www.thesportsdb.com/api/v1/json",
        "description": "Metadata de equipos y eventos.",
        "reliability_notes": "Fallback/metadata, no fuente principal de resultados.",
        "use_for": ["metadata", "teams", "players", "logos", "aliases", "events"],
        "supports_live": False,
        "supports_history": True,
        "supports_manual_import": False,
    },
    {
        "name": "StatsBomb Open Data",
        "slug": "statsbomb_open_data",
        "sport": "football",
        "rank": 90,
        "enabled_by_default": True,
        "requires_env": None,
        "base_url": "https://raw.githubusercontent.com/statsbomb/open-data/master",
        "description": "Eventos historicos abiertos (no live).",
        "reliability_notes": "Historico/modelos, no fixture actual universal.",
        "use_for": ["historical_events", "lineups", "training_data"],
        "supports_live": False,
        "supports_history": True,
        "supports_manual_import": True,
    },
    {
        "name": "FiveThirtyEight SPI",
        "slug": "fivethirtyeight_spi",
        "sport": "football",
        "rank": 70,
        "enabled_by_default": False,
        "requires_env": None,
        "base_url": "https://projects.fivethirtyeight.com",
        "description": "Ratings SPI / referencia de modelo.",
        "reliability_notes": "Referencia de modelo, no fuente oficial de resultados.",
        "use_for": ["ratings", "model_reference", "xg_reference"],
        "supports_live": False,
        "supports_history": True,
        "supports_manual_import": False,
    },
]

LOL_SOURCES = [
    {
        "name": "Riot Data Dragon",
        "slug": "riot_datadragon",
        "sport": "lol",
        "rank": 100,
        "enabled_by_default": True,
        "requires_env": None,
        "base_url": "https://ddragon.leagueoflegends.com",
        "description": "Fuente oficial para datos estaticos.",
        "reliability_notes": "Datos estaticos (parches, campeones, items).",
        "use_for": [
            "patches",
            "champions",
            "items",
            "summoner_spells",
            "runes",
            "assets",
        ],
        "supports_live": False,
        "supports_history": False,
        "supports_manual_import": False,
    },
    {
        "name": "Leaguepedia (Cargo)",
        "slug": "leaguepedia_cargo",
        "sport": "lol",
        "rank": 85,
        "enabled_by_default": True,
        "requires_env": None,
        "base_url": "https://lol.fandom.com/api.php",
        "description": "API community/Cargo (MediaWiki).",
        "reliability_notes": "Respetar rate limit y usar User-Agent claro.",
        "use_for": [
            "schedule",
            "teams",
            "players",
            "tournaments",
            "scoreboard_games",
            "scoreboard_players",
            "scoreboard_teams",
            "picks_bans",
        ],
        "supports_live": False,
        "supports_history": True,
        "supports_manual_import": False,
    },
    {
        "name": "Oracle's Elixir (CSV)",
        "slug": "oracles_elixir_csv",
        "sport": "lol",
        "rank": 85,
        "enabled_by_default": True,
        "requires_env": None,
        "base_url": "https://oracleselixir.com",
        "description": "Importador CSV historico manual.",
        "reliability_notes": "No descarga automatica obligatoria.",
        "use_for": ["historical_csv", "team_stats", "player_stats", "game_stats"],
        "supports_live": False,
        "supports_history": True,
        "supports_manual_import": True,
    },
    {
        "name": "Games of Legends (gol.gg)",
        "slug": "games_of_legends",
        "sport": "lol",
        "rank": 75,
        "enabled_by_default": False,
        "requires_env": None,
        "base_url": "https://gol.gg",
        "description": "Referencia manual / comparacion de equipos.",
        "reliability_notes": "Registrada como disabled_reference_only. Sin scraper en MVP.",
        "use_for": ["manual_reference", "team_comparison"],
        "supports_live": False,
        "supports_history": True,
        "supports_manual_import": True,
    },
    {
        "name": "Riot API",
        "slug": "riot_api",
        "sport": "lol",
        "rank": 80,
        "enabled_by_default": False,
        "requires_env": "RIOT_API_KEY",
        "base_url": "https://americas.api.riotgames.com",
        "description": "Datos de cuentas/partidas no-pro.",
        "reliability_notes": "Solo identidades confirmadas y partidas personales verificables; nunca reemplaza Leaguepedia.",
        "use_for": ["verified_personal_matches", "account_data", "summoner_data"],
        "supports_live": True,
        "supports_history": True,
        "supports_manual_import": False,
    },
    {
        "name": "Riot Esports (GRID)",
        "slug": "riot_esports_grid",
        "sport": "lol",
        "rank": 100,
        "enabled_by_default": False,
        "requires_env": "RIOT_ESPORTS_ACCESS",
        "base_url": "",
        "description": "Fuente oficial de esports en vivo (no open/free).",
        "reliability_notes": "Registrada como no implementada.",
        "use_for": ["official_live_esports"],
        "supports_live": True,
        "supports_history": True,
        "supports_manual_import": False,
    },
]

REGISTRY = FOOTBALL_SOURCES + LOL_SOURCES


def all_sources() -> list:
    return list(REGISTRY)


def sources_for(sport: str) -> list:
    return [s for s in REGISTRY if s["sport"] == sport]


def get_source(slug: str):
    for s in REGISTRY:
        if s["slug"] == slug:
            return s
    return None


def source_status(src: dict) -> str:
    """One of: enabled, disabled_missing_env, disabled_reference_only."""
    requires_env = src.get("requires_env")
    if requires_env:
        provider_map = {
            "football_data_org": "football_data_org",
            "riot_api": "riot_api",
        }
        provider_slug = provider_map.get(src["slug"])
        if provider_slug:
            from .secret_provider import SecretProvider, SecretStoreError

            try:
                value, _ = SecretProvider.get_secret(provider_slug, "api_key")
            except SecretStoreError:
                value = None
            return "enabled" if value else "disabled_missing_env"
        return "disabled_missing_env"
    return "enabled" if src.get("enabled_by_default") else "disabled_reference_only"


def is_enabled(src: dict) -> bool:
    return source_status(src) == "enabled"


def as_dict(src: dict) -> dict:
    data = dict(src)
    data["status"] = source_status(src)
    data["enabled"] = is_enabled(src)
    return data
