"""Fixed catalog of supported integrations and their credential contracts."""

PROVIDERS = {
    "football_data_org": {
        "name": "Football-data.org",
        "description": "Fixtures, resultados, equipos y tablas de football-data.org v4.",
        "secret_fields": {"api_key": "API key"},
        "test_method": "football_data_org",
        "capabilities": ["fixtures", "results", "standings", "teams"],
        "mode": "API v4 gratuita",
        "rate_limit": "10 requests/minuto",
        "data_role": "Fuente primaria de resultados, fixtures, selecciones y planteles.",
        "warning": None,
    },
    "api_football": {
        "name": "API-Football",
        "description": "Fixtures y estadísticas detalladas opcionales de fútbol.",
        "secret_fields": {"api_key": "API key"},
        "test_method": "api_football",
        "capabilities": ["fixtures", "statistics", "events", "players"],
        "mode": "Opcional/configurable",
        "rate_limit": "Según plan configurado",
        "data_role": "Detalle de fixtures; nunca simula cobertura sin clave.",
        "warning": None,
    },
    "riot_api": {
        "name": "Riot API",
        "description": "API de cuentas y partidas no profesionales de Riot.",
        "secret_fields": {"api_key": "API key"},
        "test_method": "riot_api",
        "capabilities": ["account_data", "summoner_data", "non_pro_match_data"],
        "mode": "Development o Personal API Key",
        "rate_limit": "Límites informados por Riot",
        "data_role": "Identidades confirmadas y partidas personales verificables; no esports profesional.",
        "warning": "Se recomienda Personal API Key. Development keys se consideran vencidas a las 24 horas.",
    },
    "thesportsdb": {
        "name": "TheSportsDB",
        "description": "Metadata de equipos y eventos deportivos.",
        "secret_fields": {"api_key": "API key"},
        "test_method": "thesportsdb",
        "capabilities": ["metadata", "teams", "events"],
        "mode": "Free API v1",
        "rate_limit": "30 requests/minuto",
        "data_role": "Fallback de metadata; nunca odds ni resultados primarios.",
        "warning": None,
        "public_default_value": "123",
    },
    "aposta_kambi": {
        "name": "Aposta / Kambi",
        "description": "Cuotas públicas de Aposta.LA mediante Kambi.",
        "secret_fields": {},
        "test_method": None,
        "capabilities": ["odds", "markets"],
        "mode": "Público",
        "rate_limit": None,
        "data_role": "Eventos próximos, mercados y odds.",
        "warning": None,
    },
    "leaguepedia": {
        "name": "Leaguepedia",
        "description": "Datos competitivos públicos mediante Cargo.",
        "secret_fields": {},
        "test_method": None,
        "capabilities": ["schedule", "teams", "players", "history"],
        "mode": "Cargo público",
        "rate_limit": "Uso moderado con User-Agent",
        "data_role": "Fuente primaria de series y jugadores profesionales LoL.",
        "warning": None,
    },
    "riot_datadragon": {
        "name": "Data Dragon",
        "description": "Datos estáticos públicos de Riot.",
        "secret_fields": {},
        "test_method": None,
        "capabilities": ["patches", "champions", "items", "assets"],
        "mode": "Público",
        "rate_limit": None,
        "data_role": "Datos estáticos oficiales de LoL.",
        "warning": None,
    },
    "oracles_elixir": {
        "name": "Oracle's Elixir",
        "description": "Importación histórica CSV; no requiere clave.",
        "secret_fields": {},
        "test_method": None,
        "capabilities": ["historical_csv", "team_stats", "player_stats"],
        "mode": "CSV público/manual",
        "rate_limit": None,
        "data_role": "Backfill de estadísticas profesionales LoL.",
        "warning": None,
    },
}

ENV_FALLBACKS = {
    ("football_data_org", "api_key"): "football_data_api_key",
    ("api_football", "api_key"): "api_football_api_key",
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
            "mode": item.get("mode"),
            "rate_limit": item.get("rate_limit"),
            "data_role": item.get("data_role"),
            "warning": item.get("warning"),
        }
        for slug, item in PROVIDERS.items()
    ]
