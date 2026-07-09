from fastapi import APIRouter, Depends
from sqlmodel import Session

from ..database import get_session
from ..models import Prediction
from ..schemas import OddsAnalyzeRequest, OddsAnalyzeResponse
from ..services import odds_engine

router = APIRouter(prefix="/odds", tags=["odds"])


@router.post("/analyze", response_model=OddsAnalyzeResponse)
def analyze_odds(
    payload: OddsAnalyzeRequest, session: Session = Depends(get_session)
) -> OddsAnalyzeResponse:
    implied = odds_engine.decimal_to_implied_probability(payload.odds_decimal)
    model_prob = payload.model_probability if payload.model_probability is not None else implied
    fair = odds_engine.fair_odds(model_prob)
    ev = odds_engine.expected_value(model_prob, payload.odds_decimal, payload.stake)
    risk = odds_engine.risk_label(model_prob)

    if payload.persist and payload.match_id is not None:
        prediction = Prediction(
            match_id=payload.match_id,
            market=payload.market,
            line=payload.line,
            selection=payload.selection,
            odds_decimal=payload.odds_decimal,
            implied_probability=implied,
            model_probability=model_prob,
            fair_odds=fair,
            expected_value=ev,
            risk_label=risk,
        )
        session.add(prediction)
        session.commit()

    return OddsAnalyzeResponse(
        odds_decimal=payload.odds_decimal,
        implied_probability=implied,
        model_probability=model_prob,
        fair_odds=fair,
        expected_value=ev,
        risk_label=risk,
    )
