from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..models import Sport
from ..schemas import SportCreate

router = APIRouter(prefix="/sports", tags=["sports"])


@router.post("", response_model=Sport)
def create_sport(payload: SportCreate, session: Session = Depends(get_session)) -> Sport:
    sport = Sport(**payload.model_dump())
    session.add(sport)
    session.commit()
    session.refresh(sport)
    return sport


@router.get("", response_model=list[Sport])
def list_sports(session: Session = Depends(get_session)) -> list[Sport]:
    return list(session.exec(select(Sport)).all())
