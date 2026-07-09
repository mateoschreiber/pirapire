from fastapi import APIRouter, Depends
from sqlmodel import Session, select

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
def football_matches(limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(
        select(FootballMatch).order_by(FootballMatch.start_time.desc()).limit(limit)
    ).all()


@router.get("/football/standings")
def football_standings(limit: int = 500, session: Session = Depends(get_session)) -> list:
    return session.exec(
        select(FootballStanding).order_by(FootballStanding.position).limit(limit)
    ).all()


@router.get("/lol/patches")
def lol_patches(limit: int = 100, session: Session = Depends(get_session)) -> list:
    return session.exec(select(LolPatch).order_by(LolPatch.id.desc()).limit(limit)).all()


@router.get("/lol/champions")
def lol_champions(limit: int = 500, session: Session = Depends(get_session)) -> list:
    return session.exec(select(LolChampion).order_by(LolChampion.name).limit(limit)).all()
