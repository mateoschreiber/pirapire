from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models_lol import (
    LolMatchEvent,
    LolMatchStatisticsReadModel,
    LolOddsSnapshot,
    LolTeamOdd,
)

router = APIRouter(prefix="/api/lol")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/matches/upcoming")
def upcoming_matches(
    hours: int = Query(default=48, ge=1, le=168),
    session: Session = Depends(get_session),
):
    now = _now_utc()
    window_end = now + timedelta(hours=hours)
    stmt = (
        select(LolMatchEvent)
        .where(LolMatchEvent.start_time_utc >= now)
        .where(LolMatchEvent.start_time_utc <= window_end)
        .where(LolMatchEvent.status == "scheduled")
        .order_by(LolMatchEvent.start_time_utc.asc())
    )
    matches = session.exec(stmt).all()

    result = []
    for m in matches:
        odds_a = None
        odds_b = None
        provider = None
        captured = None

        snapshot_stmt = (
            select(LolOddsSnapshot)
            .where(LolOddsSnapshot.match_event_id == m.id)
            .where(LolOddsSnapshot.is_current == True)  # noqa: E712
            .order_by(LolOddsSnapshot.captured_at.desc())
            .limit(1)
        )
        snapshot = session.exec(snapshot_stmt).first()
        if snapshot:
            provider = snapshot.provider
            captured = snapshot.captured_at.isoformat()
            odd_stmt = select(LolTeamOdd).where(LolTeamOdd.snapshot_id == snapshot.id)
            odds = session.exec(odd_stmt).all()
            for o in odds:
                if o.team_name == m.team_a:
                    odds_a = o.decimal_odds
                elif o.team_name == m.team_b:
                    odds_b = o.decimal_odds

        result.append({
            "match_key": m.match_key,
            "league": m.league,
            "tournament": m.tournament,
            "team_a": m.team_a,
            "team_b": m.team_b,
            "start_time_utc": m.start_time_utc.isoformat(),
            "best_of": m.best_of,
            "status": m.status,
            "odds_a": odds_a,
            "odds_b": odds_b,
            "odds_provider": provider,
            "odds_captured_at": captured,
        })

    return {"matches": result, "count": len(result), "window_hours": hours, "timezone": settings.app_timezone}


@router.get("/matches/{match_key}")
def get_match(match_key: str, session: Session = Depends(get_session)):
    stmt = select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)
    match = session.exec(stmt).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    odds_a = None
    odds_b = None
    provider = None
    captured = None

    snapshot_stmt = (
        select(LolOddsSnapshot)
        .where(LolOddsSnapshot.match_event_id == match.id)
        .where(LolOddsSnapshot.is_current == True)  # noqa: E712
        .order_by(LolOddsSnapshot.captured_at.desc())
        .limit(1)
    )
    snapshot = session.exec(snapshot_stmt).first()
    if snapshot:
        provider = snapshot.provider
        captured = snapshot.captured_at.isoformat()
        odd_stmt = select(LolTeamOdd).where(LolTeamOdd.snapshot_id == snapshot.id)
        odds = session.exec(odd_stmt).all()
        for o in odds:
            if o.team_name == match.team_a:
                odds_a = o.decimal_odds
            elif o.team_name == match.team_b:
                odds_b = o.decimal_odds

    return {
        "match_key": match.match_key,
        "source_name": match.source_name,
        "league": match.league,
        "tournament": match.tournament,
        "team_a": match.team_a,
        "team_b": match.team_b,
        "start_time_utc": match.start_time_utc.isoformat(),
        "best_of": match.best_of,
        "status": match.status,
        "source_url": match.source_url,
        "odds_a": odds_a,
        "odds_b": odds_b,
        "odds_provider": provider,
        "odds_captured_at": captured,
    }


@router.get("/matches/{match_key}/statistics")
def get_match_statistics(match_key: str, session: Session = Depends(get_session)):
    stmt = select(LolMatchStatisticsReadModel).where(LolMatchStatisticsReadModel.match_key == match_key)
    stats = session.exec(stmt).first()

    from ..services.lol_metrics_engine import compute_match_statistics
    if not stats or stats.status != "computed":
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

    return {
        "match_key": stats.match_key,
        "status": stats.status,
        "payload": stats.payload_json,
        "coverage": stats.coverage_json,
        "computed_at": stats.computed_at.isoformat(),
    }
