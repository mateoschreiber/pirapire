from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models_history import ComboHistory, ComboLegHistory, PredictionHistory
from ..services import history_service

router = APIRouter(tags=["history"])


@router.get("/history/predictions")
def list_predictions(limit: int = 100, session: Session = Depends(get_session)) -> list:
    return session.exec(
        select(PredictionHistory).order_by(PredictionHistory.id.desc()).limit(limit)
    ).all()


@router.get("/history/combos")
def list_combos(limit: int = 100, session: Session = Depends(get_session)) -> list:
    combos = session.exec(
        select(ComboHistory).order_by(ComboHistory.id.desc()).limit(limit)
    ).all()
    result = []
    for combo in combos:
        legs = session.exec(
            select(ComboLegHistory)
            .where(ComboLegHistory.combo_id == combo.id)
            .order_by(ComboLegHistory.leg_order)
        ).all()
        result.append({"combo": combo, "legs": legs})
    return result


@router.post("/history/predictions/{prediction_id}/settle")
def settle_prediction(
    prediction_id: int,
    result: str = Body(..., embed=True),
    session: Session = Depends(get_session),
) -> PredictionHistory:
    prediction = session.get(PredictionHistory, prediction_id)
    if prediction is None:
        raise HTTPException(status_code=404, detail="prediction not found")
    try:
        return history_service.settle(session, prediction, result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/history/combos/{combo_id}/settle")
def settle_combo(
    combo_id: int,
    result: str = Body(..., embed=True),
    session: Session = Depends(get_session),
) -> ComboHistory:
    combo = session.get(ComboHistory, combo_id)
    if combo is None:
        raise HTTPException(status_code=404, detail="combo not found")
    try:
        return history_service.settle(session, combo, result)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
