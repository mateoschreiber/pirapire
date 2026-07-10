from __future__ import annotations

from datetime import datetime
from difflib import SequenceMatcher
import re
import unicodedata

from sqlmodel import Session, select

from ..models_football import FootballCompetition, FootballMatch, FootballTeam
from ..models_imports import ImportedOdds
from . import lol_aposta_matcher


def normalize_name(value: str | None) -> str:
    text = (value or '').strip().lower()
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r'[^a-z0-9 ]+', ' ', text)
    text = re.sub(r'\b(fc|cf|club|de|the|team|esports|e sports|gaming)\b', ' ', text)
    return ' '.join(text.split())


def ratio(a: str | None, b: str | None) -> float:
    na, nb = normalize_name(a), normalize_name(b)
    if not na or not nb:
        return 0.0
    if na == nb:
        return 1.0
    if na in nb or nb in na:
        return 0.9
    return SequenceMatcher(None, na, nb).ratio()


def date_score(a: datetime | None, b: datetime | None) -> float:
    if not a or not b:
        return 0.55
    diff_hours = abs((a.replace(tzinfo=None) - b.replace(tzinfo=None)).total_seconds()) / 3600
    if diff_hours <= 8:
        return 1.0
    if diff_hours <= 36:
        return 0.85
    if diff_hours <= 120:
        return 0.65
    return 0.25


def unmatched() -> dict:
    return {
        'matched_source': None,
        'matched_event_id': None,
        'match_confidence': 0.0,
        'match_reason': 'no comparable event found',
    }


def football(session: Session, odd: ImportedOdds) -> dict:
    teams = {t.id: t for t in session.exec(select(FootballTeam)).all()}
    comps = {c.id: c for c in session.exec(select(FootballCompetition)).all()}
    best = None
    for match in session.exec(select(FootballMatch)).all():
        home = teams.get(match.home_team_id)
        away = teams.get(match.away_team_id)
        if not home or not away:
            continue
        direct = (ratio(odd.team_a, home.name) + ratio(odd.team_b, away.name)) / 2
        swapped = (ratio(odd.team_a, away.name) + ratio(odd.team_b, home.name)) / 2
        team_score = max(direct, swapped)
        comp = comps.get(match.competition_id)
        comp_score = ratio(odd.competition, comp.name if comp else None)
        dscore = date_score(odd.event_date, match.start_time)
        confidence = 0.68 * team_score + 0.17 * comp_score + 0.15 * dscore
        if best is None or confidence > best['match_confidence']:
            best = {
                'matched_source': 'football_match',
                'matched_event_id': match.id,
                'match_confidence': round(confidence, 3),
                'match_reason': f'teams={team_score:.2f}; competition={comp_score:.2f}; date={dscore:.2f}',
                'home_team_id': match.home_team_id,
                'away_team_id': match.away_team_id,
                'home_team_name': home.name,
                'away_team_name': away.name,
            }
    return best or unmatched()


def lol(session: Session, odd: ImportedOdds) -> dict:
 return lol_aposta_matcher.match_imported_odd(session, odd)


def match_imported_odd(session: Session, odd: ImportedOdds) -> dict:
    if odd.sport == 'football':
        return football(session, odd)
    if odd.sport == 'lol':
        return lol(session, odd)
    return unmatched()
