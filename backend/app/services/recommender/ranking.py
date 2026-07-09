"""Scoring and ranking of recommendations by mode.

Modes:
- probability: highest chance of winning (ignores margin/payout).
- profit: highest expected value.
- odds: highest decimal odds (accepts more risk).
- balanced: weighted blend minus a risk penalty.
"""

RISK_PENALTY = {"low": 0.0, "medium": 0.34, "high": 0.67, "very_high": 1.0}
MODES = ("probability", "profit", "odds", "balanced")


def compute_scores(rec: dict) -> dict:
    prob = rec.get("model_probability") or 0.0
    ev = rec.get("expected_value") or 0.0
    implied = rec.get("implied_probability") or 0.0

    rec["probability_score"] = max(0.0, min(1.0, prob))
    rec["odds_score"] = max(0.0, min(1.0, 1.0 - implied))
    rec["profit_score"] = max(0.0, min(1.0, ev))
    risk_penalty = RISK_PENALTY.get(rec.get("risk_label"), 0.5)
    rec["balanced_score"] = (
        0.45 * rec["probability_score"]
        + 0.25 * rec["profit_score"]
        + 0.20 * rec["odds_score"]
        - 0.10 * risk_penalty
    )
    return rec


def _sort_key(mode: str):
    if mode == "probability":
        return lambda r: (
            r.get("model_probability", 0.0),
            -RISK_PENALTY.get(r.get("risk_label"), 0.5),
            r.get("odds_decimal", 0.0),
        )
    if mode == "profit":
        return lambda r: (r.get("expected_value", 0.0), r.get("model_probability", 0.0))
    if mode == "odds":
        return lambda r: (r.get("odds_decimal", 0.0), r.get("model_probability", 0.0))
    return lambda r: (r.get("balanced_score", 0.0),)


def rank_score_for(rec: dict, mode: str) -> float:
    if mode == "probability":
        return rec.get("model_probability", 0.0)
    if mode == "profit":
        return rec.get("expected_value", 0.0)
    if mode == "odds":
        return rec.get("odds_decimal", 0.0)
    return rec.get("balanced_score", 0.0)


def rank(recs: list, mode: str) -> list:
    if mode not in MODES:
        mode = "probability"
    for rec in recs:
        compute_scores(rec)
        rec["rank_score"] = rank_score_for(rec, mode)
        rec["rank_mode"] = mode
    return sorted(recs, key=_sort_key(mode), reverse=True)
