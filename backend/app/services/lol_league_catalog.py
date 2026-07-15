import json

from sqlmodel import Session, select

from ..models_lol import LolLeague, LolLeagueAlias
from .lol_team_aliases import normalize_text

ACTIVE_LEAGUES = {
    'LCK': {'name': 'League of Legends Champions Korea', 'region': 'Korea', 'tier': 'tier1', 'aliases': ['LCK', 'Champions Korea']},
    'LPL': {'name': 'League of Legends Pro League', 'region': 'China', 'tier': 'tier1', 'aliases': ['LPL', 'Pro League']},
    'LEC': {'name': 'League of Legends EMEA Championship', 'region': 'EMEA', 'tier': 'tier1', 'aliases': ['LEC', 'EMEA Championship', 'EU LCS']},
    'LCS': {'name': 'League Championship Series', 'region': 'North America', 'tier': 'tier1', 'aliases': ['LCS', 'NA LCS', 'LTA North']},
    'CBLOL': {'name': 'Campeonato Brasileiro de League of Legends', 'region': 'Brazil', 'tier': 'tier1', 'aliases': ['CBLOL', 'Brasil', 'LTA South']},
    'LCP': {'name': 'League of Legends Championship Pacific', 'region': 'Pacific', 'tier': 'tier1', 'aliases': ['LCP', 'Pacific Championship', 'PCS', 'VCS', 'LJL']},
    'MSI': {'name': 'Mid-Season Invitational', 'region': 'International', 'tier': 'international', 'aliases': ['MSI', 'Mid-Season Invitational']},
    'WORLDS': {'name': 'World Championship', 'region': 'International', 'tier': 'international', 'aliases': ['Worlds', 'World Championship', 'Campeonato Mundial', 'Mundial', 'WORLDS']},
    'FIRST_STAND': {'name': 'First Stand', 'region': 'International', 'tier': 'international', 'aliases': ['First Stand', 'FST', 'FIRST_STAND']},
}

LEGACY_LEAGUES = {
    'LTA': {'name': 'League of The Americas', 'region': 'Americas', 'tier': 'legacy', 'aliases': ['LTA', 'LTA North', 'LTA South']},
    'LLA': {'name': 'Liga Latinoamerica', 'region': 'LATAM', 'tier': 'legacy', 'aliases': ['LLA', 'LATAM']},
    'PCS': {'name': 'Pacific Championship Series', 'region': 'Pacific', 'tier': 'legacy', 'aliases': ['PCS']},
    'VCS': {'name': 'Vietnam Championship Series', 'region': 'Vietnam', 'tier': 'legacy', 'aliases': ['VCS']},
    'LJL': {'name': 'League of Legends Japan League', 'region': 'Japan', 'tier': 'legacy', 'aliases': ['LJL']},
    'LCO': {'name': 'League of Legends Circuit Oceania', 'region': 'Oceania', 'tier': 'legacy', 'aliases': ['LCO']},
    'TCL': {'name': 'Turkish Championship League', 'region': 'Turkey', 'tier': 'legacy', 'aliases': ['TCL']},
    'LCL': {'name': 'League of Legends Continental League', 'region': 'CIS', 'tier': 'legacy', 'aliases': ['LCL']},
}


def all_leagues(include_legacy: bool = True) -> dict:
    data = dict(ACTIVE_LEAGUES)
    if include_legacy:
        data.update(LEGACY_LEAGUES)
    return data


def canonical_league(value: str | None) -> str | None:
    normalized = normalize_text(value)
    if not normalized:
        return None
    for slug, meta in all_leagues(True).items():
        if normalize_text(slug) == normalized:
            return slug
        for alias in meta.get('aliases', []):
            if normalize_text(alias) == normalized:
                return slug
    if normalized in ('world championship', 'worlds'):
        return 'WORLDS'
    return (value or '').strip().upper() or None


def seed_catalog(session: Session) -> dict:
    leagues = 0
    aliases = 0
    for slug, meta in all_leagues(True).items():
        row = session.exec(select(LolLeague).where(LolLeague.slug == slug)).first()
        if row is None:
            row = LolLeague(slug=slug, name=meta['name'])
            leagues += 1
        row.name = meta['name']
        row.region = meta.get('region')
        row.tier = meta.get('tier')
        row.active = slug in ACTIVE_LEAGUES
        row.current_name = meta['name']
        row.legacy_names_json = json.dumps(meta.get('aliases', []))
        session.add(row)
        for alias in [slug] + meta.get('aliases', []):
            normalized = normalize_text(alias)
            existing = session.exec(select(LolLeagueAlias).where(LolLeagueAlias.normalized_alias == normalized, LolLeagueAlias.canonical_league == slug)).first()
            if not existing:
                session.add(LolLeagueAlias(canonical_league=slug, alias=alias, normalized_alias=normalized))
                aliases += 1
    session.commit()
    return {'leagues_upserted': leagues, 'aliases_upserted': aliases}
