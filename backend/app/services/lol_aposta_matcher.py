from difflib import SequenceMatcher

from sqlmodel import Session, select

from ..config import settings
from ..models_imports import ImportedOdds
from ..models_lol import LolTeamGameStat
from .lol_league_catalog import ACTIVE_LEAGUES, canonical_league
from .lol_team_aliases import canonical_team, normalize_text


def ratio(a: str | None, b: str | None) -> float:
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.9
    return SequenceMatcher(None, na, nb).ratio()


def league_supported(league: str | None, include_lower_tiers: bool = False) -> bool:
    if not league:
        return include_lower_tiers
    if league in ACTIVE_LEAGUES:
        return True
    return include_lower_tiers


def match_imported_odd(session: Session, odd: ImportedOdds, include_lower_tiers: bool = False) -> dict:
    league = canonical_league(odd.competition)
    if not league_supported(league, include_lower_tiers):
        return {
            'matched_source': None,
            'matched_event_id': None,
            'match_confidence': 0.0,
            'match_reason': 'league unsupported or outside active whitelist',
            'league': league,
            'coverage_status': 'unsupported',
        }
    team_a = canonical_team(session, odd.team_a, league) or odd.team_a
    team_b = canonical_team(session, odd.team_b, league) or odd.team_b
    rows = session.exec(select(LolTeamGameStat).where(LolTeamGameStat.league == league)).all()
    best = None
    for row in rows:
        if not row.team_name or not row.opponent_name:
            continue
        direct = (ratio(team_a, row.team_name) + ratio(team_b, row.opponent_name)) / 2
        swapped = (ratio(team_a, row.opponent_name) + ratio(team_b, row.team_name)) / 2
        team_score = max(direct, swapped)
        confidence = 0.82 * team_score + 0.18
        if best is None or confidence > best['match_confidence']:
            best = {
                'matched_source': 'lol_history',
                'matched_event_id': row.game_id,
                'match_confidence': round(confidence, 3),
                'match_reason': 'league=%s; teams=%.2f' % (league, team_score),
                'league': league,
                'lol_team_name': team_a,
                'lol_opponent_name': team_b,
            }
    if best:
        return best
    return {
        'matched_source': None,
        'matched_event_id': None,
        'match_confidence': 0.0,
        'match_reason': 'no LoL history rows for league/team pair',
        'league': league,
        'lol_team_name': team_a,
        'lol_opponent_name': team_b,
    }
