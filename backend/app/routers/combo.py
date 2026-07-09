from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..database import get_session
from ..schemas import ComboAnalyzeRequest, ComboAnalyzeResponse
from ..services import combo_engine, history_service, odds_engine

router = APIRouter(prefix="/combo", tags=["combo"])


@router.post("/analyze", response_model=ComboAnalyzeResponse)
def analyze_combo(
    payload: ComboAnalyzeRequest, session: Session = Depends(get_session)
) -> ComboAnalyzeResponse:
    probabilities = [leg.probability for leg in payload.legs]
    combo_prob = combo_engine.calculate_naive_combo_probability(probabilities)
    fair = combo_engine.calculate_combo_fair_odds(combo_prob)

    offered = payload.offered_odds
    if offered is None:
        product = 1.0
        has_odds = False
        for leg in payload.legs:
            if leg.odds_decimal:
                product *= leg.odds_decimal
                has_odds = True
        offered = product if has_odds else None

    expected = None
    if offered is not None:
        expected = combo_engine.calculate_combo_expected_value(combo_prob, offered, payload.stake)

    risk = odds_engine.risk_label(combo_prob)

    combo_id = None
    if payload.save:
        analysis = {
            "combo_probability": combo_prob,
            "combo_fair_odds": fair,
            "offered_odds": offered,
            "expected_value": expected,
            "risk_label": risk,
        }
        legs = [leg.model_dump() for leg in payload.legs]
        saved = history_service.save_combo(session, payload.name, payload.sport, analysis, legs)
        combo_id = saved.id

    return ComboAnalyzeResponse(
        combo_probability=combo_prob,
        combo_fair_odds=fair,
        offered_odds=offered,
        expected_value=expected,
        risk_label=risk,
        legs=len(payload.legs),
        combo_id=combo_id,
    )
