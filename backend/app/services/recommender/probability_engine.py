"""Estimate model probability + coverage for a selection."""

from sqlmodel import Session

from ..features import football_features, lol_features


def estimate(session: Session, sport: str, market_code: str, odds_decimal: float, context: dict = None) -> dict:
    implied = (1.0 / odds_decimal) if odds_decimal and odds_decimal > 0 else 0.0
    model = None
    coverage = None

    if market_code:
        if sport == "football":
            model, coverage = football_features.estimate(session, market_code, odds_decimal, context)
        elif sport == "lol":
            model, coverage = lol_features.estimate(session, market_code, odds_decimal, context)
    else:
        coverage = "unsupported"

    if model is None:
        model = implied
        if coverage is None:
            coverage = "odds_implied_only"

    return {
        "model_probability": model,
        "implied_probability": implied,
        "coverage_status": coverage,
    }
