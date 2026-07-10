from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..models_football import (
    FootballCompetition,
    FootballMatch,
    FootballStanding,
    FootballTeam,
)
from ..models_lol import LolChampion, LolPatch

router = APIRouter(prefix="/data", tags=["data"])


@router.get("/football/competitions")
def football_competitions(limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(select(FootballCompetition).limit(limit)).all()


@router.get("/football/teams")
def football_teams(limit: int = 500, session: Session = Depends(get_session)) -> list:
    return session.exec(select(FootballTeam).order_by(FootballTeam.name).limit(limit)).all()


@router.get("/football/matches")
def football_matches(status: str | None = None, limit: int = 200, session: Session = Depends(get_session)) -> list:
    query = select(FootballMatch)
    if status:
        query = query.where(FootballMatch.status == status.upper())
    return session.exec(query.order_by(FootballMatch.start_time.asc()).limit(limit)).all()


@router.get("/football/standings")
def football_standings(limit: int = 500, session: Session = Depends(get_session)) -> list:
    return session.exec(
        select(FootballStanding).order_by(FootballStanding.position).limit(limit)
    ).all()


def _naive(dt) -> datetime | None:
    if dt is None:
        return None
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt


@router.get("/football/status")
def football_status(session: Session = Depends(get_session)) -> dict:
    competitions = session.exec(select(func.count()).select_from(FootballCompetition)).one()
    total_matches = session.exec(select(func.count()).select_from(FootballMatch)).one()
    future_matches = session.exec(
        select(func.count()).select_from(FootballMatch)
        .where(FootballMatch.start_time > datetime.now(UTC))
    ).one()
    finished_matches = session.exec(
        select(func.count()).select_from(FootballMatch)
        .where(FootballMatch.status == 'FINISHED')
    ).one()

    last_match = session.exec(
        select(FootballMatch).order_by(FootballMatch.retrieved_at.desc())
    ).first()

    stale_hours = getattr(settings, 'source_stale_hours', 12)
    stale_threshold = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=stale_hours)
    last_retrieved = _naive(last_match.retrieved_at) if last_match else None

    return {
        'last_sync': last_match.retrieved_at.isoformat() if last_match and last_match.retrieved_at else None,
        'stale': not last_match or not last_retrieved or last_retrieved < stale_threshold,
        'competitions_configured': settings.football_data_competitions,
        'competitions_processed': competitions,
        'future_matches': future_matches,
        'finished_matches': finished_matches,
        'total_matches': total_matches,
        'lookback_days': settings.sync_default_lookback_days,
        'lookahead_days': settings.sync_default_lookahead_days,
        'max_competitions_per_run': settings.football_data_max_competitions_per_run,
    }


@router.get("/lol/patches")
def lol_patches(limit: int = 100, session: Session = Depends(get_session)) -> list:
    return session.exec(select(LolPatch).order_by(LolPatch.id.desc()).limit(limit)).all()


@router.get("/lol/champions")
def lol_champions(limit: int = 500, session: Session = Depends(get_session)) -> list:
    return session.exec(select(LolChampion).order_by(LolChampion.name).limit(limit)).all()
