import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models_lol import LolMatchEvent, LolOddsSnapshot, LolTeamOdd

router = APIRouter(prefix="/api/lol")

COMPETITIONS = (
    ("LCK", "LCK"),
    ("LPL", "LPL"),
    ("LEC", "LEC"),
    ("LTA", "LTA"),
    ("LCP", "LCP"),
    ("WORLDS", "WORLDS"),
    ("MSI", "MSI"),
    ("FIRST_STAND", "FIRST STAND"),
    ("EWC", "EWC"),
)
COMPETITION_LABELS = dict(COMPETITIONS)


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _competition_code(league: str | None, tournament: str | None = None) -> str | None:
    league_text = (league or "").strip().upper()
    combined = f"{league_text} {(tournament or '').strip().upper()}"
    if "ESPORTS WORLD CUP" in combined:
        return "EWC"
    if "FIRST STAND" in combined or "FIST STAND" in combined:
        return "FIRST_STAND"
    if "MID-SEASON INVITATIONAL" in combined or re.search(r"(^|[^A-Z])MSI([^A-Z]|$)", combined):
        return "MSI"
    if "WORLD CHAMPIONSHIP" in combined or "WORLDS" in combined:
        return "WORLDS"
    for code in ("LCK", "LPL", "LEC", "LTA", "LCP"):
        if re.match(rf"^{code}(?:/|$)", league_text):
            return code
    return None


def _odds_for_match(session: Session, match: LolMatchEvent) -> dict:
    snapshot = session.exec(
        select(LolOddsSnapshot)
        .where(LolOddsSnapshot.match_event_id == match.id)
        .where(LolOddsSnapshot.is_current == True)  # noqa: E712
        .order_by(LolOddsSnapshot.captured_at.desc())
        .limit(1)
    ).first()
    odds_a = odds_b = None
    if snapshot:
        for odd in session.exec(select(LolTeamOdd).where(LolTeamOdd.snapshot_id == snapshot.id)).all():
            if odd.team_name == match.team_a:
                odds_a = odd.decimal_odds
            elif odd.team_name == match.team_b:
                odds_b = odd.decimal_odds
    available = odds_a is not None and odds_b is not None
    return {
        "odds_a": odds_a,
        "odds_b": odds_b,
        "odds_provider": snapshot.provider if snapshot else None,
        "odds_captured_at": snapshot.captured_at.isoformat() if snapshot else None,
        "odds_available": available,
        "odds_status": "available" if available else "not_captured",
        "odds_message": None if available else "Sin captura de cuotas. Oracle's Elixir no incluye datos de apuestas.",
    }


def _match_view(session: Session, match: LolMatchEvent) -> dict:
    code = _competition_code(match.league, match.tournament)
    return {
        "match_key": match.match_key,
        "competition_code": code,
        "competition": COMPETITION_LABELS.get(code, match.league or match.tournament or "N/D"),
        "league": match.league,
        "tournament": match.tournament,
        "team_a": match.team_a,
        "team_b": match.team_b,
        "start_time_utc": match.start_time_utc.isoformat(),
        "best_of": match.best_of,
        "status": match.status,
        **_odds_for_match(session, match),
    }


def _competition_summary(events: list[LolMatchEvent], upcoming: list[LolMatchEvent], year: int) -> list[dict]:
    upcoming_counts = {code: 0 for code, _ in COMPETITIONS}
    for event in upcoming:
        code = _competition_code(event.league, event.tournament)
        if code:
            upcoming_counts[code] += 1
    result = []
    for code, label in COMPETITIONS:
        relevant = [
            event for event in events
            if event.start_time_utc.year == year and _competition_code(event.league, event.tournament) == code
        ]
        teams = sorted({
            team.strip()
            for event in relevant
            for team in (event.team_a, event.team_b)
            if team and team.strip().upper() not in {"TBD", "TBA", "UNKNOWN"}
        }, key=str.casefold)
        result.append({
            "code": code,
            "label": label,
            "season": year,
            "qualified_teams": teams,
            "team_count": len(teams),
            "upcoming_matches": upcoming_counts[code],
            "coverage": "available" if teams else "not_published",
        })
    return result


@router.get("/matches/upcoming")
def upcoming_matches(
    hours: int = Query(default=48, ge=1, le=720),
    session: Session = Depends(get_session),
):
    now = _now_utc()
    window_end = now + timedelta(hours=hours)
    scheduled = session.exec(
        select(LolMatchEvent)
        .where(LolMatchEvent.start_time_utc >= now)
        .where(LolMatchEvent.start_time_utc <= window_end)
        .where(LolMatchEvent.status == "scheduled")
        .order_by(LolMatchEvent.start_time_utc.asc())
    ).all()
    allowed = [event for event in scheduled if _competition_code(event.league, event.tournament)]
    all_events = session.exec(select(LolMatchEvent)).all()
    return {
        "matches": [_match_view(session, match) for match in allowed],
        "competitions": _competition_summary(all_events, allowed, now.year),
        "allowed_competitions": [label for _, label in COMPETITIONS],
        "count": len(allowed),
        "window_hours": hours,
        "timezone": settings.app_timezone,
    }


@router.get("/matches/{match_key}")
def get_match(match_key: str, session: Session = Depends(get_session)):
    match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return {
        **_match_view(session, match),
        "source_name": match.source_name,
        "source_url": match.source_url,
    }


@router.get("/matches/{match_key}/statistics")
def get_match_statistics(match_key: str, session: Session = Depends(get_session)):
    from ..services.lol_metrics_engine import compute_match_statistics

    result = compute_match_statistics(session, match_key)
    if not result:
        raise HTTPException(status_code=404, detail="Match not found")
    payload, coverage = result
    return {
        "match_key": match_key,
        "status": "computed",
        "payload": payload,
        "coverage": coverage,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
