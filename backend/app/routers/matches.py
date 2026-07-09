from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models import Match
from ..schemas import MatchCreate

router = APIRouter(prefix="/matches", tags=["matches"])


@router.post("", response_model=Match)
def create_match(payload: MatchCreate, session: Session = Depends(get_session)) -> Match:
    match = Match(**payload.model_dump())
    session.add(match)
    session.commit()
    session.refresh(match)
    return match


@router.get("", response_model=list[Match])
def list_matches(session: Session = Depends(get_session)) -> list[Match]:
    return list(session.exec(select(Match)).all())
