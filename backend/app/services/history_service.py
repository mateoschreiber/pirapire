"""Persistence helpers for prediction and combo history."""

import json
from datetime import UTC, datetime

from sqlmodel import Session

from ..models_history import ComboHistory, ComboLegHistory, PredictionHistory

VALID_RESULTS = {"won", "lost", "void", "pending"}


def save_prediction(session: Session, payload: dict, analysis: dict) -> PredictionHistory:
    prediction = PredictionHistory(
        sport=payload.get("sport"),
        match_label=payload.get("match_label"),
        market_code=payload.get("market_code") or payload.get("market"),
        market_text=payload.get("market_text"),
        line=payload.get("line"),
        selection=payload.get("selection"),
        odds_decimal=analysis["odds_decimal"],
        model_probability=analysis.get("model_probability"),
        implied_probability=analysis["implied_probability"],
        fair_odds=analysis["fair_odds"],
        expected_value=analysis["expected_value"],
        risk_label=analysis["risk_label"],
        source_context_json=json.dumps(payload.get("source_context")) if payload.get("source_context") else None,
        status="pending",
    )
    session.add(prediction)
    session.commit()
    session.refresh(prediction)
    return prediction


def save_combo(session: Session, name, sport, analysis: dict, legs: list) -> ComboHistory:
    combo = ComboHistory(
        sport=sport,
        name=name,
        offered_odds=analysis.get("offered_odds"),
        model_probability=analysis.get("combo_probability"),
        fair_odds=analysis["combo_fair_odds"],
        expected_value=analysis.get("expected_value"),
        risk_label=analysis["risk_label"],
        status="pending",
    )
    session.add(combo)
    session.commit()
    session.refresh(combo)
    for order, leg in enumerate(legs, start=1):
        session.add(
            ComboLegHistory(
                combo_id=combo.id,
                market_code=leg.get("market_code"),
                market_text=leg.get("market_text"),
                line=leg.get("line"),
                selection=leg.get("selection"),
                odds_decimal=leg.get("odds_decimal"),
                model_probability=leg.get("probability"),
                implied_probability=(1.0 / leg["odds_decimal"]) if leg.get("odds_decimal") else 0.0,
                risk_label=leg.get("risk_label"),
                leg_order=order,
            )
        )
    session.commit()
    return combo


def settle(session: Session, item, result: str) -> object:
    result = (result or "").strip().lower()
    if result not in VALID_RESULTS:
        raise ValueError(f"invalid result '{result}' (allowed: {sorted(VALID_RESULTS)})")
    item.result = None if result == "pending" else result
    item.status = "pending" if result == "pending" else "settled"
    item.settled_at = None if result == "pending" else datetime.now(UTC)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
