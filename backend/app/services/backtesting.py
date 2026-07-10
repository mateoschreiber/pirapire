"""Walk-forward backtesting for football prediction models."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from ..models_football import FootballMatch
from ..models_recommendations import BetRecommendation
from .features.football_features import PoissonModel


def backtest_1x2(session: Session, min_matches: int = 20, step_days: int = 30) -> dict:
    matches = session.exec(
        select(FootballMatch)
        .where(FootballMatch.home_score.is_not(None), FootballMatch.status == 'FINISHED')
        .order_by(FootballMatch.start_time)
    ).all()

    if len(matches) < min_matches:
        return {"error": "insufficient_data", "total_matches": len(matches)}

    results = []
    brier_scores = []
    correct = 0
    total = 0

    for i in range(min_matches, len(matches)):
        train = matches[:i]
        test_match = matches[i]

        model = PoissonModel(train, ref_date=test_match.start_time)
        if model.sample_size < 10:
            continue

        pred = model.predict_match(test_match.home_team_id, test_match.away_team_id)

        home_result = (test_match.home_score or 0) > (test_match.away_score or 0)
        away_result = (test_match.home_score or 0) < (test_match.away_score or 0)
        draw_result = (test_match.home_score or 0) == (test_match.away_score or 0)

        if home_result:
            actual = 'home'
        elif away_result:
            actual = 'away'
        else:
            actual = 'draw'

        prob = pred[actual]

        brier = (1.0 - prob) ** 2
        brier_scores.append(brier)

        if prob >= 0.35:  # only count if model is reasonably confident
            correct += 1 if (
                (actual == 'home' and pred['home'] > pred['away'] and pred['home'] > pred['draw']) or
                (actual == 'away' and pred['away'] > pred['home'] and pred['away'] > pred['draw']) or
                (actual == 'draw' and pred['draw'] > pred['home'] and pred['draw'] > pred['away'])
            ) else 0
            total += 1

    if not brier_scores:
        return {"error": "no_predictions", "total_matches": len(matches)}

    avg_brier = sum(brier_scores) / len(brier_scores)
    accuracy = correct / total if total > 0 else 0.0

    return {
        "total_matches": len(matches),
        "tested_pairs": len(brier_scores),
        "brier_score": round(avg_brier, 4),
        "accuracy": round(accuracy, 4),
        "correct": correct,
        "total_predictions": total,
        "benchmark_brier": round(sum([((1.0/3.0) - 1.0) ** 2 / 3.0 * 3 for _ in brier_scores]) / len(brier_scores), 4),
        "model_version": "poisson_v1",
    }


def backtest_over_under(session: Session, line: float = 2.5, min_matches: int = 20) -> dict:
    matches = session.exec(
        select(FootballMatch)
        .where(FootballMatch.home_score.is_not(None), FootballMatch.status == 'FINISHED')
        .order_by(FootballMatch.start_time)
    ).all()

    if len(matches) < min_matches:
        return {"error": "insufficient_data"}

    brier_scores = []
    correct = 0
    total = 0

    for i in range(min_matches, len(matches)):
        train = matches[:i]
        test_match = matches[i]

        model = PoissonModel(train, ref_date=test_match.start_time)
        if model.sample_size < 10:
            continue

        pred = model.predict_match(test_match.home_team_id, test_match.away_team_id)
        total_goals = (test_match.home_score or 0) + (test_match.away_score or 0)
        actual_over = total_goals > line

        prob_over = sum(p for g, p in pred['goal_probs'].items() if g > line)
        prob = prob_over if actual_over else (1.0 - prob_over)

        brier = (1.0 - prob) ** 2
        brier_scores.append(brier)

        if (prob_over >= 0.5 and actual_over) or (prob_over < 0.5 and not actual_over):
            correct += 1
        total += 1

    if not brier_scores:
        return {"error": "no_predictions"}

    return {
        "line": line,
        "tested_pairs": len(brier_scores),
        "brier_score": round(sum(brier_scores) / len(brier_scores), 4),
        "accuracy": round(correct / total, 4) if total > 0 else 0,
        "correct": correct,
        "total_predictions": total,
        "model_version": "poisson_v1",
    }
