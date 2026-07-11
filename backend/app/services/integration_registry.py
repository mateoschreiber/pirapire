"""Fixed catalog of supported integrations and their credential contracts."""

PROVIDERS = {
    "football_data_org": {
        "name": "Football-data.org",
        "description": "Fixtures, resultados, equipos y tablas de football-data.org v4.",
        "secret_fields": {"api_key": "API key"},
        "test_method": "football_data_org",
        "capabilities": ["fixtures", "results", "standings", "teams"],
    },
    "riot_api": {
        "name": "Riot API",
        "description": "API de cuentas y partidas no profesionales de Riot.",
        "secret_fields": {"api_key": "API key"},
        "test_method": "riot_api",
        "capabilities": ["account_data", "summoner_data", "non_pro_match_data"],
    },
    "thesportsdb": {
        "name": "TheSportsDB",
        "description": "Metadata de equipos y eventos deportivos.",
        "secret_fields": {"api_key": "API key"},
        "test_method": "thesportsdb",
        "capabilities": ["metadata", "teams", "events"],
    },
    "aposta_kambi": {
        "name": "Aposta / Kambi",
        "description": "Cuotas públicas de Aposta.LA mediante Kambi.",
        "secret_fields": {},
        "test_method": None,
        "capabilities": ["odds", "markets"],
    },
    "leaguepedia": {
        "name": "Leaguepedia",
        "description": "Datos competitivos públicos mediante Cargo.",
        "secret_fields": {},
        "test_method": None,
        "capabilities": ["schedule", "teams", "players", "history"],
    },
    "riot_datadragon": {
        "name": "Data Dragon",
        "description": "Datos estáticos públicos de Riot.",
        "secret_fields": {},
        "test_method": None,
        "capabilities": ["patches", "champions", "items", "assets"],
    },
    "oracles_elixir": {
        "name": "Oracle's Elixir",
        "description": "Importación histórica CSV; no requiere clave.",
        "secret_fields": {},
        "test_method": None,
        "capabilities": ["historical_csv", "team_stats", "player_stats"],
    },
}

ENV_FALLBACKS = {
    ("football_data_org", "api_key"): "football_data_api_key",
    ("riot_api", "api_key"): "riot_api_key",
    ("thesportsdb", "api_key"): "thesportsdb_api_key",
}


def get_provider(slug: str) -> dict | None:
    provider = PROVIDERS.get(slug)
    return dict(provider) if provider else None


def public_catalog() -> list[dict]:
    return [
        {
            "slug": slug,
            "name": item["name"],
            "description": item["description"],
            "credential_names": list(item["secret_fields"]),
            "requires_key": bool(item["secret_fields"]),
            "capabilities": list(item["capabilities"]),
        }
        for slug, item in PROVIDERS.items()
    ]
