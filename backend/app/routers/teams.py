from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models import Team
from ..schemas import TeamCreate

router = APIRouter(prefix="/teams", tags=["teams"])


@router.post("", response_model=Team)
def create_team(payload: TeamCreate, session: Session = Depends(get_session)) -> Team:
    team = Team(**payload.model_dump())
    session.add(team)
    session.commit()
    session.refresh(team)
    return team


@router.get("", response_model=list[Team])
def list_teams(session: Session = Depends(get_session)) -> list[Team]:
    return list(session.exec(select(Team)).all())
