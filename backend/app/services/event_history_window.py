"""Phase 4B41 — strict per-event history windows (data-only, no network).

For every football Aposta event we build a per-team window of exactly 10
FINISHED fixtures whose kickoff is strictly before the event kickoff
(cutoff_utc). The event's own match (the anchor) is always excluded, even if
its listed time differs, so an event never uses its own result or anything
after its kickoff. The anchor fixture is preserved in the raw fixture table and
may legitimately appear in the window of a *later* event.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import UTC, datetime

from sqlmodel import Session, delete, select

from ..models_football import EventTeamHistoryWindow, FootballFixtureStat
from ..models_imports import ImportedOdds

PROVIDER = "fresh_football"
WINDOW_N = 10

# Aposta.LA (Spanish) -> source (English) country names, mirrored from the
# fresh-football ingester so window matching works across languages.
ES_EN_COUNTRY = {
    "suiza": "Switzerland", "noruega": "Norway", "inglaterra": "England",
    "argentina": "Argentina", "brasil": "Brazil", "espana": "Spain",
    "alemania": "Germany", "francia": "France", "italia": "Italy",
    "belgica": "Belgium", "paises bajos": "Netherlands", "holanda": "Netherlands",
    "croacia": "Croatia", "portugal": "Portugal", "uruguay": "Uruguay",
    "estados unidos": "United States", "mexico": "Mexico", "corea del sur": "South Korea",
    "japon": "Japan", "marruecos": "Morocco", "senegal": "Senegal",
}


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _deaccent(value) -> str:
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _english_name(name: str) -> str:
    return ES_EN_COUNTRY.get(_deaccent(name), name)


def _accepted_names(name: str) -> set[str]:
    return {_norm(name), _norm(_english_name(name))}


def _as_utc(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _distinct_events(session: Session) -> list[dict]:
    """Distinct football events by (event_key, teams, kickoff)."""
    rows = session.exec(
        select(
            ImportedOdds.event_key, ImportedOdds.team_a, ImportedOdds.team_b,
            ImportedOdds.kickoff_utc,
        ).where(ImportedOdds.sport == "football", ImportedOdds.event_key.is_not(None))
    ).all()
    events = {}
    for ek, a, b, k in rows:
        if not ek or k is None:
            continue
        if ek not in events:
            events[ek] = {"event_key": ek, "team_a": a, "team_b": b, "kickoff": _as_utc(k)}
    return list(events.values())


def _team_fixtures(session: Session, team: str) -> list[FootballFixtureStat]:
    accepted = _accepted_names(team)
    rows = session.exec(
        select(FootballFixtureStat).where(
            FootballFixtureStat.provider == PROVIDER,
            FootballFixtureStat.team_name.in_({team, _english_name(team)}),
        )
    ).all()
    # keep only rows whose canonical team really matches (defensive)
    return [r for r in rows if _norm(r.team_name) in accepted]


def _is_anchor(fixture: FootballFixtureStat, other_team: str, cutoff: datetime) -> bool:
    """True if this fixture is the event's own match (head-to-head near cutoff),
    regardless of small time-format differences."""
    opp_accepted = _accepted_names(other_team)
    if _norm(fixture.opponent_name) not in opp_accepted:
        return False
    k = _as_utc(fixture.kickoff_utc)
    if k is None:
        return True  # unknown time for the exact head-to-head -> exclude to be safe
    # Same match if within ~2 days of the cutoff (covers re-listed kickoff times).
    return abs((k - cutoff).total_seconds()) <= 2 * 86400


def build_windows(session: Session) -> dict:
    """Rebuild EventTeamHistoryWindow for every football event. Idempotent."""
    events = _distinct_events(session)
    now = datetime.now(UTC)
    session.exec(delete(EventTeamHistoryWindow))
    session.commit()

    report = {}
    for ev in events:
        cutoff = ev["kickoff"]
        ek = ev["event_key"]
        for team, other in ((ev["team_a"], ev["team_b"]), (ev["team_b"], ev["team_a"])):
            if not team:
                continue
            fixtures = _team_fixtures(session, team)
            # strictly before cutoff and not the anchor match
            candidates = []
            for f in fixtures:
                k = _as_utc(f.kickoff_utc)
                if k is None or k >= cutoff:
                    continue
                if _is_anchor(f, other, cutoff):
                    continue
                candidates.append((k, f))
            candidates.sort(key=lambda x: x[0], reverse=True)
            chosen = candidates[:WINDOW_N]
            for rank, (k, f) in enumerate(chosen, start=1):
                skey = f"{ek}|{_norm(team)}|{f.source_id or f.fixture_id}"
                session.add(EventTeamHistoryWindow(
                    event_key=ek, team=team,
                    fixture_source_id=str(f.source_id or f.fixture_id),
                    rank=rank, cutoff_utc=cutoff, opponent=f.opponent_name,
                    kickoff_utc=k, provider=PROVIDER, source_key=skey,
                    created_at=now, updated_at=now,
                ))
            report.setdefault(ek, {})[team] = {
                "count": len(chosen),
                "cutoff": cutoff.isoformat(),
                "first": chosen[0][0].isoformat() if chosen else None,
                "last": chosen[-1][0].isoformat() if chosen else None,
                "opponents": [f.opponent_name for _, f in chosen],
            }
        session.commit()
    return report


def window_for(session: Session, event_key: str, team: str) -> list[EventTeamHistoryWindow]:
    """Return the strict window rows for an event/team ordered by rank."""
    return session.exec(
        select(EventTeamHistoryWindow)
        .where(EventTeamHistoryWindow.event_key == event_key,
               EventTeamHistoryWindow.team == team)
        .order_by(EventTeamHistoryWindow.rank)
    ).all()
