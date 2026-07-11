from fastapi.testclient import TestClient

from app.database import Session, engine
from app.main import app
from app.models_imports import ImportedOdds
from app.services.recommender import combo_builder, probability_engine, ranking

client = TestClient(app)


def _rec(prob, ev, odds, risk="medium"):
    return {
        "model_probability": prob,
        "expected_value": ev,
        "odds_decimal": odds,
        "implied_probability": 1.0 / odds,
        "risk_label": risk,
    }


def test_mode_probability_orders_by_model_probability():
    recs = [_rec(0.4, 0.1, 3.0), _rec(0.8, 0.0, 1.5), _rec(0.6, 0.2, 2.0)]
    ranked = ranking.rank(recs, "probability")
    probs = [r["model_probability"] for r in ranked]
    assert probs == sorted(probs, reverse=True)
    assert ranked[0]["model_probability"] == 0.8


def test_mode_profit_orders_by_expected_value():
    recs = [_rec(0.5, 0.05, 2.0), _rec(0.5, 0.30, 2.0), _rec(0.5, -0.10, 2.0)]
    ranked = ranking.rank(recs, "profit")
    evs = [r["expected_value"] for r in ranked]
    assert evs == sorted(evs, reverse=True)
    assert ranked[0]["expected_value"] == 0.30


def test_mode_odds_orders_by_odds():
    recs = [_rec(0.5, 0.0, 2.0), _rec(0.5, 0.0, 5.0), _rec(0.5, 0.0, 3.0)]
    ranked = ranking.rank(recs, "odds")
    odds = [r["odds_decimal"] for r in ranked]
    assert odds == sorted(odds, reverse=True)
    assert ranked[0]["odds_decimal"] == 5.0


def test_balanced_sets_rank_score():
    recs = [_rec(0.6, 0.1, 2.0)]
    ranked = ranking.rank(recs, "balanced")
    assert "balanced_score" in ranked[0]
    assert ranked[0]["rank_score"] == ranked[0]["balanced_score"]


def _single(event, market, prob, odds, risk="low"):
    return {
        "event_label": event,
        "market_code": market,
        "line": None,
        "sport": "football",
        "selection_text": "x",
        "model_probability": prob,
        "odds_decimal": odds,
        "implied_probability": 1.0 / odds,
        "expected_value": prob * (odds - 1) - (1 - prob),
        "risk_label": risk,
    }


def test_combo_builder_does_not_mix_same_event_or_market():
    singles = [
        _single("A vs B", "total_goals_over_under", 0.7, 1.8),
        _single("C vs D", "match_winner", 0.65, 1.9),
        _single("A vs B", "match_winner", 0.6, 2.0),
    ]
    combos = combo_builder.build(singles, "probability", max_legs=3, max_combos=10)
    for combo in combos:
        events = [leg["event_label"] for leg in combo["legs"]]
        assert len(set(events)) == len(events)


def test_combo_builder_limits_legs_and_count():
    singles = [_single(f"E{i} vs X", f"m{i}", 0.7, 1.8) for i in range(8)]
    combos = combo_builder.build(singles, "probability", max_legs=3, max_combos=5)
    assert len(combos) <= 5
    for combo in combos:
        assert 2 <= combo["legs_count"] <= 3


def test_probability_engine_unsupported_and_implied():
    with Session(engine) as session:
        est = probability_engine.estimate(session, "football", None, 2.0, {})
        assert est["coverage_status"] == "insufficient_data"
        est2 = probability_engine.estimate(session, "football", "match_winner", 2.0, {})
        assert est2["coverage_status"] in ("insufficient_data", "odds_implied_only", "heuristic", "model")
        assert abs(est2["implied_probability"] - 0.5) < 1e-9


def test_recommendation_run_and_bets_ordered_by_odds():
    with Session(engine) as session:
        for i in range(4):
            session.add(
                ImportedOdds(
                    batch_id=1,
                    sport="football",
                    market_text="Total de goles",
                    market_code="total_goals_over_under",
                    line=2.5,
                    selection="over",
                    odds_decimal=1.8 + i * 0.3,
                    normalized_key=f"rec-test-{i}",
                    team_a=f"Team{i}",
                    team_b=f"Opp{i}",
                )
            )
        session.commit()

    resp = client.post("/recommendations/run", json={"mode": "odds", "min_probability": 0})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_recommendations"] >= 0

    bets = client.get("/recommendations/bets?mode=odds").json()
    assert len(bets) >= 0
    odds = [b["odds_decimal"] for b in bets]
    assert odds == sorted(odds, reverse=True)
