import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models_markets import MarketAlias, MarketCatalog
from ..services import market_catalog

router = APIRouter(prefix="/markets", tags=["markets"])


def _market_dict(m: MarketCatalog) -> dict:
    return {
        "id": m.id,
        "sport": m.sport,
        "market_code": m.market_code,
        "display_name": m.display_name,
        "category": m.category,
        "source_status": m.source_status,
        "risk_level": m.risk_level,
        "enabled": m.enabled,
        "data_requirements": json.loads(m.data_requirements_json) if m.data_requirements_json else [],
    }


@router.get("")
def list_markets(sport: str | None = None, session: Session = Depends(get_session)) -> list:
    query = select(MarketCatalog)
    if sport:
        query = query.where(MarketCatalog.sport == sport)
    return [_market_dict(m) for m in session.exec(query).all()]


@router.get("/aliases")
def list_aliases(session: Session = Depends(get_session)) -> list:
    return session.exec(select(MarketAlias)).all()


@router.post("/seed")
def seed_markets(session: Session = Depends(get_session)) -> dict:
    result = market_catalog.seed_catalog(session)
    result["status"] = "ok"
    return result


@router.get("/{market_id}")
def get_market(market_id: int, session: Session = Depends(get_session)) -> dict:
    market = session.get(MarketCatalog, market_id)
    if market is None:
        raise HTTPException(status_code=404, detail="market not found")
    data = _market_dict(market)
    data["aliases"] = [
        {"alias_text": a.alias_text, "normalized_alias": a.normalized_alias}
        for a in session.exec(select(MarketAlias).where(MarketAlias.market_id == market_id)).all()
    ]
    return data
