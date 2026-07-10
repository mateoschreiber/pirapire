"""In-code definition of the Market Catalog (football + LoL markets)."""

FOOTBALL_MARKETS = {
    "match_winner": {"display": "Ganador del partido", "category": "result", "risk": "low"},
    "double_chance": {"display": "Doble oportunidad", "category": "result", "risk": "low"},
    "total_goals_over_under": {"display": "Total de goles (over/under)", "category": "totals", "risk": "medium"},
    "team_goals_over_under": {"display": "Goles de equipo (over/under)", "category": "totals", "risk": "medium"},
    "both_teams_to_score": {"display": "Ambos equipos anotan", "category": "totals", "risk": "medium"},
    "half_time_full_time": {"display": "Descanso / Resultado Final", "category": "result", "risk": "high"},
    "cards_over_under": {"display": "Total de tarjetas (over/under)", "category": "cards", "risk": "high"},
    "corners_over_under": {"display": "Total de corners (over/under)", "category": "corners", "risk": "high"},
    "shots_on_target_over_under": {"display": "Tiros a puerta (over/under)", "category": "shots", "risk": "high"},
    "team_shots_on_target_over_under": {"display": "Tiros a puerta de equipo (over/under)", "category": "shots", "risk": "high"},
    "player_shots_on_target_over_under": {"display": "Tiros a puerta del jugador (over/under)", "category": "player", "risk": "very_high"},
    "player_cards": {"display": "Tarjetas del jugador", "category": "player", "risk": "very_high"},
    "anytime_goalscorer": {"display": "Goleador en cualquier momento", "category": "player", "risk": "very_high"},
}

LOL_MARKETS = {
    "map_winner": {"display": "Ganador del mapa", "category": "result", "risk": "low"},
    "series_winner": {"display": "Ganador de la serie", "category": "result", "risk": "low"},
    "total_kills_over_under": {"display": "Total de kills (over/under)", "category": "totals", "risk": "medium"},
    "team_kills_over_under": {"display": "Kills de equipo (over/under)", "category": "totals", "risk": "medium"},
    "player_kills_over_under": {"display": "Kills del jugador (over/under)", "category": "player", "risk": "high"},
    "player_deaths_over_under": {"display": "Muertes del jugador (over/under)", "category": "player", "risk": "high"},
    "role_kills_over_under": {"display": "Kills por rol (over/under)", "category": "player", "risk": "high"},
    "total_towers_over_under": {"display": "Total de torretas (over/under)", "category": "objectives", "risk": "medium"},
    "team_towers_over_under": {"display": "Torretas de equipo (over/under)", "category": "objectives", "risk": "medium"},
    "total_inhibitors_over_under": {"display": "Total de inhibidores (over/under)", "category": "objectives", "risk": "medium"},
    "team_inhibitors_over_under": {"display": "Inhibidores de equipo (over/under)", "category": "objectives", "risk": "medium"},
    "game_duration_over_under": {"display": "Duración del mapa (over/under)", "category": "game", "risk": "medium"},
    "first_blood": {"display": "Primera sangre", "category": "game", "risk": "medium"},
    "dragons_over_under": {"display": "Total de dragones (over/under)", "category": "objectives", "risk": "medium"},
    "barons_over_under": {"display": "Total de barones (over/under)", "category": "objectives", "risk": "medium"},
}

# ---- Aliases (Spanish text from Aposta.LA -> market_code) ----
FOOTBALL_ALIASES = [
    ('Resultado', 'match_winner'),
    ('Ganador', 'match_winner'),
    ('Equipo gana', 'match_winner'),
    ('1X2', 'match_winner'),
    ('Superior a', 'total_goals_over_under'),
    ('Inferior a', 'total_goals_over_under'),
    ('Total', 'total_goals_over_under'),
    ('Handicap', 'team_goals_over_under'),
    ("Ganador del partido", "match_winner"),
    ("Empate no en juego", "match_winner"),
    ("Ganador del partido (sin empate)", "match_winner"),
    ("Doble oportunidad", "double_chance"),
    ("Total de goles", "total_goals_over_under"),
    ("Total goles", "total_goals_over_under"),
    ("Más de", "total_goals_over_under"),
    ("Menos de", "total_goals_over_under"),
    ("Total de goles local", "team_goals_over_under"),
    ("Total de goles visitante", "team_goals_over_under"),
    ("Ambos equipos anotan", "both_teams_to_score"),
    ("Ambos marcan", "both_teams_to_score"),
    ("Resultado al descanso", "half_time_full_time"),
    ("Descanso", "half_time_full_time"),
    ("Descanso /", "half_time_full_time"),
    ("Medio tiempo", "half_time_full_time"),
    ("Total de tarjetas", "cards_over_under"),
    ("Tarjetas", "cards_over_under"),
    ("Total de corners", "corners_over_under"),
    ("Corners", "corners_over_under"),
    ("Tiros a puerta total", "shots_on_target_over_under"),
    ("Tiros a puerta del equipo", "team_shots_on_target_over_under"),
    ("Tiros a puerta del jugador", "player_shots_on_target_over_under"),
]

LOL_ALIASES = [
    ("Ganador del mapa", "map_winner"),
    ("Mapa 1 ganador", "map_winner"),
    ("Mapa 2 ganador", "map_winner"),
    ("Mapa 3 ganador", "map_winner"),
    ("Ganador de la serie", "series_winner"),
    ("Total de kills", "total_kills_over_under"),
    ("Total kills", "total_kills_over_under"),
    ("Kills del equipo", "team_kills_over_under"),
    ("Asesinatos del jugador", "player_kills_over_under"),
    ("Muertes del jugador", "player_deaths_over_under"),
    ("Total de torretas", "total_towers_over_under"),
    ("Total de torretas destruidas", "total_towers_over_under"),
    ("Torretas", "total_towers_over_under"),
    ("Inhibidores", "total_inhibitors_over_under"),
    ("Total de inhibidores", "total_inhibitors_over_under"),
    ("Duración del mapa", "game_duration_over_under"),
    ("Duración mapa", "game_duration_over_under"),
    ("Primera sangre", "first_blood"),
    ("Dragones", "dragons_over_under"),
    ("Total de dragones", "dragons_over_under"),
    ("Barones", "barons_over_under"),
    ("Total de barones", "barons_over_under"),
]

ALL_MARKETS = {**FOOTBALL_MARKETS, **LOL_MARKETS}
FOOTBALL_CODES = set(FOOTBALL_MARKETS)
LOL_CODES = set(LOL_MARKETS)
ALL_ALIASES = FOOTBALL_ALIASES + LOL_ALIASES

# Default availability per market (best-effort with current connectors).
SUPPORTED_CODES = {
    "match_winner", "double_chance", "total_goals_over_under", "both_teams_to_score",
    "half_time_full_time", "map_winner", "series_winner", "game_duration_over_under",
    "total_kills_over_under", "team_kills_over_under", "total_towers_over_under",
    "team_towers_over_under", "total_inhibitors_over_under", "first_blood",
    "dragons_over_under", "barons_over_under",
}
MANUAL_ONLY_CODES = {
    "cards_over_under", "corners_over_under", "shots_on_target_over_under",
    "team_shots_on_target_over_under", "player_shots_on_target_over_under",
    "player_cards", "anytime_goalscorer", "player_kills_over_under",
    "player_deaths_over_under", "role_kills_over_under", "team_goals_over_under",
    "team_inhibitors_over_under",
}


def _source_status(code: str) -> str:
    if code in SUPPORTED_CODES:
        return "supported"
    if code in MANUAL_ONLY_CODES:
        return "manual_only"
    return "partial"


def seed_catalog(session) -> dict:
    """Idempotently seed MarketCatalog + MarketAlias. Returns counts."""
    import json

    from ..models_markets import MarketAlias, MarketCatalog
    from .market_mapper import normalize_text

    markets_upserted = 0
    for sport, markets in (("football", FOOTBALL_MARKETS), ("lol", LOL_MARKETS)):
        for code, meta in markets.items():
            existing = session.exec(
                _select_market(MarketCatalog, sport, code)
            ).first()
            if existing is None:
                session.add(
                    MarketCatalog(
                        sport=sport,
                        market_code=code,
                        display_name=meta["display"],
                        category=meta.get("category"),
                        source_status=_source_status(code),
                        risk_level=meta.get("risk", "medium"),
                        data_requirements_json=json.dumps(meta.get("requires", [])),
                        enabled=True,
                    )
                )
                markets_upserted += 1
            else:
                existing.display_name = meta["display"]
                existing.category = meta.get("category")
                existing.source_status = _source_status(code)
                existing.risk_level = meta.get("risk", "medium")
                session.add(existing)
    session.commit()

    # Aliases: rebuild against the seeded markets.
    catalog = {(m.sport, m.market_code): m for m in session.exec(_select_all(MarketCatalog)).all()}
    aliases_upserted = 0
    existing_aliases = {
        (a.market_id, a.normalized_alias)
        for a in session.exec(_select_all(MarketAlias)).all()
    }
    for sport, alias_list in (("football", FOOTBALL_ALIASES), ("lol", LOL_ALIASES)):
        for alias_text, code in alias_list:
            market = catalog.get((sport, code))
            if market is None:
                continue
            normalized = normalize_text(alias_text)
            if (market.id, normalized) in existing_aliases:
                continue
            session.add(
                MarketAlias(
                    market_id=market.id,
                    alias_text=alias_text,
                    normalized_alias=normalized,
                    bookmaker="ApostaLA",
                    language="es",
                )
            )
            existing_aliases.add((market.id, normalized))
            aliases_upserted += 1
    session.commit()
    return {"markets_upserted": markets_upserted, "aliases_upserted": aliases_upserted}


def _select_market(model, sport, code):
    from sqlmodel import select

    return select(model).where(model.sport == sport, model.market_code == code)


def _select_all(model):
    from sqlmodel import select

    return select(model)

