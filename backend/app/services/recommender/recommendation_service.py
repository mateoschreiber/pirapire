"""Generate single + combo bet recommendations from available odds."""

import json
from datetime import UTC, datetime

from sqlmodel import Session, select

from ...config import settings
from ...models_aposta import ApostaEvent, ApostaMarket, ApostaSelection
from ...models_imports import ImportedOdds
from ...models_recommendations import (
    BetRecommendation,
    ComboRecommendation,
    ComboRecommendationLeg,
    RecommendationRun,
)
from .. import odds_engine
from . import combo_builder, probability_engine, ranking


def _gather_candidates(session: Session) -> list[dict]:
    candidates = []

    for o in session.exec(select(ImportedOdds)).all():
        event_label = " vs ".join([p for p in [o.team_a, o.team_b] if p]) or (o.competition or "Evento")
        candidates.append(
            {
                "sport": o.sport,
                "event_label": event_label,
                "market_id": o.market_id,
                "market_code": o.market_code,
                "market_text": o.market_text,
                "selection_text": o.selection,
                "line": o.line,
                "odds_decimal": o.odds_decimal,
                "source": "imported_odds",
            }
        )

    # ApostaSelection (present only if a future browser worker populated them).
    rows = session.exec(select(ApostaSelection)).all()
    if rows:
        markets = {m.id: m for m in session.exec(select(ApostaMarket)).all()}
        events = {e.id: e for e in session.exec(select(ApostaEvent)).all()}
        for sel in rows:
            if not sel.is_active:
                continue
            market = markets.get(sel.market_id)
            event = events.get(market.event_id) if market else None
            label = None
            if event:
                label = " vs ".join([p for p in [event.team_a, event.team_b] if p]) or event.event_name
            candidates.append(
                {
                    "sport": event.sport if event else None,
                    "event_label": label or "Evento",
                    "market_id": market.market_id if market else None,
                    "market_code": market.market_code if market else None,
                    "market_text": market.market_text if market else None,
                    "selection_text": sel.selection_text,
                    "line": market.line if market else None,
                    "odds_decimal": sel.odds_decimal,
                    "source": "aposta",
                }
            )
    return candidates


def _build_recommendation(session: Session, cand: dict) -> dict:
    odds = cand["odds_decimal"]
    est = probability_engine.estimate(
        session,
        cand.get("sport"),
        cand.get("market_code"),
        odds,
        {"line": cand.get("line"), "selection": cand.get("selection_text")},
    )
    model_prob = est["model_probability"]
    implied = est["implied_probability"]
    fair = (1.0 / model_prob) if model_prob > 0 else 0.0
    ev = model_prob * (odds - 1.0) - (1.0 - model_prob)
    risk = odds_engine.risk_label(model_prob) if 0 < model_prob <= 1 else "high"
    rec = dict(cand)
    rec.update(
        {
            "model_probability": model_prob,
            "implied_probability": implied,
            "fair_odds": fair,
            "expected_value": ev,
            "risk_label": risk,
            "coverage_status": est["coverage_status"],
        }
    )
    return rec


def run(
    session: Session,
    mode: str = None,
    sport: str = None,
    min_probability: float = None,
    min_odds: float = None,
    max_odds: float = None,
    max_legs: int = None,
    max_suggestions: int = None,
) -> dict:
    mode = mode or settings.recommender_default_mode
    if mode not in ranking.MODES:
        mode = "probability"
    min_probability = settings.recommender_min_probability if min_probability is None else min_probability
    max_legs = settings.recommender_max_combo_legs if max_legs is None else max_legs
    max_suggestions = settings.recommender_max_suggestions if max_suggestions is None else max_suggestions

    run_row = RecommendationRun(mode=mode, sport=sport, status="running")
    session.add(run_row)
    session.commit()
    session.refresh(run_row)

    candidates = _gather_candidates(session)
    recs = []
    for cand in candidates:
        if sport and cand.get("sport") != sport:
            continue
        odds = cand.get("odds_decimal")
        if not odds or odds <= 1:
            continue
        if min_odds is not None and odds < min_odds:
            continue
        if max_odds is not None and odds > max_odds:
            continue
        rec = _build_recommendation(session, cand)
        if mode != "odds" and rec["model_probability"] < min_probability:
            continue
        recs.append(rec)

    ranked = ranking.rank(recs, mode)
    top = ranked[:max_suggestions]

    for rec in top:
        row = BetRecommendation(
            run_id=run_row.id,
            sport=rec.get("sport"),
            event_label=rec.get("event_label"),
            market_id=rec.get("market_id"),
            market_code=rec.get("market_code"),
            market_text=rec.get("market_text"),
            selection_text=rec.get("selection_text"),
            line=rec.get("line"),
            odds_decimal=rec["odds_decimal"],
            implied_probability=rec["implied_probability"],
            model_probability=rec["model_probability"],
            fair_odds=rec["fair_odds"],
            expected_value=rec["expected_value"],
            probability_score=rec.get("probability_score", 0.0),
            profit_score=rec.get("profit_score", 0.0),
            odds_score=rec.get("odds_score", 0.0),
            balanced_score=rec.get("balanced_score", 0.0),
            rank_score=rec.get("rank_score", 0.0),
            rank_mode=mode,
            risk_label=rec.get("risk_label"),
            coverage_status=rec.get("coverage_status"),
            source_context_json=json.dumps({"source": rec.get("source")}),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        rec["id"] = row.id

    # Combos from the strongest singles (respect min_probability unless odds mode).
    combo_pool = top if mode == "odds" else [r for r in top if r["model_probability"] >= min_probability]
    combos = combo_builder.build(combo_pool, mode, max_legs=max_legs, max_combos=max_suggestions)
    for combo in combos:
        crow = ComboRecommendation(
            run_id=run_row.id,
            sport=combo.get("sport"),
            name=" + ".join(leg.get("event_label", "") for leg in combo["legs"]),
            legs_count=combo["legs_count"],
            offered_odds=combo["offered_odds"],
            model_probability=combo["model_probability"],
            fair_odds=combo["fair_odds"],
            expected_value=combo["expected_value"],
            probability_score=combo.get("probability_score", 0.0),
            profit_score=combo.get("profit_score", 0.0),
            odds_score=combo.get("odds_score", 0.0),
            balanced_score=combo.get("balanced_score", 0.0),
            rank_score=combo.get("rank_score", 0.0),
            rank_mode=mode,
            risk_label=combo.get("risk_label"),
        )
        session.add(crow)
        session.commit()
        session.refresh(crow)
        for order, leg in enumerate(combo["legs"], start=1):
            session.add(
                ComboRecommendationLeg(
                    combo_id=crow.id,
                    recommendation_id=leg.get("id"),
                    leg_order=order,
                    market_code=leg.get("market_code"),
                    market_text=leg.get("market_text"),
                    selection_text=leg.get("selection_text"),
                    line=leg.get("line"),
                    odds_decimal=leg.get("odds_decimal"),
                    model_probability=leg.get("model_probability", 0.0),
                )
            )
        session.commit()

    run_row.status = "success"
    run_row.finished_at = datetime.now(UTC)
    run_row.total_candidates = len(candidates)
    run_row.total_recommendations = len(top)
    run_row.message = f"{len(top)} singles, {len(combos)} combos (mode={mode})"
    session.add(run_row)
    session.commit()
    session.refresh(run_row)

    return {
        "run_id": run_row.id,
        "mode": mode,
        "status": run_row.status,
        "total_candidates": len(candidates),
        "total_recommendations": len(top),
        "total_combos": len(combos),
    }
