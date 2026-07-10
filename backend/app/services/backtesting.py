"""Walk-forward backtesting with proper Brier multiclass for 1X2."""
from __future__ import annotations

from datetime import datetime

from sqlmodel import Session, select

from ..models_football import FootballMatch
from .features.football_features import CorrectedPoissonModel


def backtest_1x2(session: Session, min_matches: int = 20) -> dict:
    matches = session.exec(
        select(FootballMatch)
        .where(FootballMatch.home_score.is_not(None), FootballMatch.status == 'FINISHED')
        .order_by(FootballMatch.start_time)
    ).all()

    if len(matches) < min_matches:
        return {"error": "insufficient_data", "total_matches": len(matches)}

    brier_scores = []
    correct = 0
    total = 0
    outcomes = {'home': 0, 'draw': 0, 'away': 0}

    for i in range(min_matches, len(matches)):
        train = matches[:i]
        test_match = matches[i]

        model = CorrectedPoissonModel(train, test_match.home_team_id, test_match.away_team_id,
                                       ref_date=test_match.start_time)
        if model.effective_sample < 3:
            continue

        pred = model.predict_match(test_match.home_team_id, test_match.away_team_id)

        if (test_match.home_score or 0) > (test_match.away_score or 0):
            actual = 'home'
        elif (test_match.home_score or 0) < (test_match.away_score or 0):
            actual = 'away'
        else:
            actual = 'draw'
        outcomes[actual] = outcomes.get(actual, 0) + 1

        # Multiclass Brier: (1-p_actual)^2 + sum(p_other^2)
        prob_home = pred['home']
        prob_draw = pred['draw']
        prob_away = pred['away']
        if actual == 'home':
            brier = (1 - prob_home)**2 + prob_draw**2 + prob_away**2
        elif actual == 'draw':
            brier = prob_home**2 + (1 - prob_draw)**2 + prob_away**2
        else:
            brier = prob_home**2 + prob_draw**2 + (1 - prob_away)**2
        brier_scores.append(brier)

        predicted = max(('home', prob_home), ('draw', prob_draw), ('away', prob_away), key=lambda x: x[1])[0]
        if predicted == actual:
            correct += 1
        total += 1

    if not brier_scores:
        return {"error": "no_predictions"}

    # Baseline: always predict the most common outcome
    most_common = max(outcomes, key=outcomes.get)
    baseline_correct = outcomes[most_common]
    baseline_acc = baseline_correct / total if total else 0

    return {
        "total_matches": len(matches),
        "tested_pairs": len(brier_scores),
        "brier_score": round(sum(brier_scores) / len(brier_scores), 4),
        "accuracy": round(correct / total, 4) if total else 0,
        "correct": correct, "total_predictions": total,
        "baseline_accuracy": round(baseline_acc, 4),
        "model_version": "poisson_corrected_v2",
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
    over_count = 0

    for i in range(min_matches, len(matches)):
        train = matches[:i]
        test_match = matches[i]

        model = CorrectedPoissonModel(train, test_match.home_team_id, test_match.away_team_id,
                                       ref_date=test_match.start_time)
        if model.effective_sample < 3:
            continue

        pred = model.predict_match(test_match.home_team_id, test_match.away_team_id)
        total_goals = (test_match.home_score or 0) + (test_match.away_score or 0)
        actual_over = total_goals > line
        if actual_over:
            over_count += 1

        prob_over = sum(p for g, p in pred['goal_probs'].items() if g > line)
        prob = prob_over if actual_over else (1.0 - prob_over)
        brier = (1.0 - prob) ** 2
        brier_scores.append(brier)

        predicted_over = prob_over >= 0.5
        if predicted_over == actual_over:
            correct += 1
        total += 1

    if not brier_scores:
        return {"error": "no_predictions"}

    baseline_rate = over_count / total if total else 0.5
    baseline_brier = baseline_rate * (1 - baseline_rate)**2 + (1 - baseline_rate) * baseline_rate**2

    return {
        "line": line,
        "tested_pairs": len(brier_scores),
        "brier_score": round(sum(brier_scores) / len(brier_scores), 4),
        "accuracy": round(correct / total, 4) if total else 0,
        "correct": correct, "total_predictions": total,
        "baseline_brier": round(baseline_brier, 4),
        "model_version": "poisson_corrected_v2",
        "validated": (correct / total) > 0.55 if total > 10 else False,
    }
