"""Poisson football model with Dixon-Coles adjustment, attack/defense ratings, home advantage, and time decay."""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional

from sqlmodel import Session, select

from ...models_football import FootballMatch

ESTIMATED_ONLY = {
    'cards_over_under', 'corners_over_under', 'shots_on_target_over_under',
    'team_shots_on_target_over_under', 'player_shots_on_target_over_under',
    'player_cards', 'anytime_goalscorer',
}


def _decay_weight(match_date, ref_date: datetime, half_life_days: float = 365.0) -> float:
    """Exponential time decay: weight = 2^(-days/half_life)."""
    if match_date is None:
        return 0.5
    if isinstance(match_date, str):
        try:
            match_date = datetime.fromisoformat(match_date.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return 0.5
    if not isinstance(match_date, datetime):
        return 0.5
    days = (ref_date - match_date.replace(tzinfo=None)).days
    return math.pow(2.0, -max(0, days) / half_life_days)


def _poisson_prob(lmbda: float, k: int) -> float:
    """Poisson probability mass function."""
    if lmbda <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lmbda) * (lmbda ** k) / math.factorial(k)


def _score_probability(home_lambda: float, away_lambda: float, max_goals: int = 10) -> dict:
    """Calculate match outcome probabilities from Poisson lambdas."""
    home_win = draw = away_win = 0.0
    goal_probs = defaultdict(float)

    for i in range(max_goals + 1):
        for j in range(max_goals + 1):
            p = _poisson_prob(home_lambda, i) * _poisson_prob(away_lambda, j)
            if i > j:
                home_win += p
            elif i == j:
                draw += p
            else:
                away_win += p
            goal_probs[i + j] += p

    return {
        'home': home_win,
        'draw': draw,
        'away': away_win,
        'goal_probs': dict(goal_probs),
    }


class PoissonModel:
    """Poisson model with Dixon-Coles adjustment for football match prediction."""

    def __init__(self, matches: list, ref_date: datetime | None = None):
        self.ref_date = ref_date or datetime.utcnow()
        self.home_advantage = 0.0
        self.team_attack: dict[int, float] = defaultdict(lambda: 0.0)
        self.team_defense: dict[int, float] = defaultdict(lambda: 0.0)
        self.league_avg = 1.35  # average goals per team per match
        self.rho = -0.06  # Dixon-Coles low-score correlation
        self.sample_size = 0
        self._fit(matches)

    def _fit(self, matches: list):
        """Fit Poisson model parameters from match history."""
        if not matches:
            return

        home_goals = defaultdict(list)
        away_goals = defaultdict(list)
        valid_matches = []

        for m in matches:
            if m.home_score is None or m.away_score is None:
                continue
            if m.home_team_id is None or m.away_team_id is None:
                continue
            weight = _decay_weight(m.start_time, self.ref_date)
            valid_matches.append((m, weight))

        if not valid_matches:
            return

        self.sample_size = len(valid_matches)

        # Calculate league average goals
        total_goals = sum((m.home_score or 0) + (m.away_score or 0) for m, w in valid_matches)
        total_weight = sum(w for _, w in valid_matches)
        if total_weight > 0:
            self.league_avg = max(0.5, total_goals / (total_weight * 2))  # per team

        # Iterative fitting (simplified: 3 iterations)
        teams = set()
        for m, _ in valid_matches:
            teams.add(m.home_team_id)
            teams.add(m.away_team_id)

        for _ in range(3):
            for team in teams:
                atk = []
                dfs = []
                for m, w in valid_matches:
                    if m.home_team_id == team:
                        atk.append((m.home_score or 0, w))
                    if m.away_team_id == team:
                        atk.append((m.away_score or 0, w))
                        dfs.append((m.home_score or 0, w))
                    if m.home_team_id != team and m.away_team_id != team:
                        continue

                if atk:
                    total = sum(g * w for g, w in atk)
                    tw = sum(w for _, w in atk)
                    self.team_attack[team] = max(0.3, total / max(tw, 0.01)) / max(self.league_avg, 0.5)

            # Home advantage
            hg = sum((m.home_score or 0) * w for m, w in valid_matches)
            ag = sum((m.away_score or 0) * w for m, w in valid_matches)
            if total_weight > 0:
                self.home_advantage = max(-0.5, min(1.0, (hg - ag) / total_weight / max(self.league_avg, 0.5)))

    def predict_match(self, home_id: int, away_id: int) -> dict:
        """Predict outcome probabilities for a specific match."""
        home_atk = self.team_attack.get(home_id, 1.0)
        home_def = self.team_defense.get(home_id, 1.0)
        away_atk = self.team_attack.get(away_id, 1.0)
        away_def = self.team_defense.get(away_id, 1.0)

        home_lambda = max(0.1, self.league_avg * home_atk * away_def + self.home_advantage)
        away_lambda = max(0.1, self.league_avg * away_atk * home_def)

        probs = _score_probability(home_lambda, away_lambda)

        # Dixon-Coles adjustment for low scores
        if self.rho and self.rho != 0:
            for i in range(2):
                for j in range(2):
                    pij = _poisson_prob(home_lambda, i) * _poisson_prob(away_lambda, j)
                    if i == 0 and j == 0:
                        adj = pij * (1.0 + home_lambda * away_lambda * self.rho)
                    elif i == 0 and j == 1:
                        adj = pij * (1.0 - home_lambda * self.rho)
                    elif i == 1 and j == 0:
                        adj = pij * (1.0 - away_lambda * self.rho)
                    elif i == 1 and j == 1:
                        adj = pij * (1.0 + self.rho)
                    else:
                        continue

                    if i == 0 and j == 0:
                        probs['draw'] -= pij
                        probs['draw'] += adj * (i == j)
                        if i > j:
                            probs['home'] -= pij
                            probs['home'] += adj
                        elif i < j:
                            probs['away'] -= pij
                            probs['away'] += adj

        return {
            'home': max(0.05, min(0.95, probs['home'])),
            'draw': max(0.05, min(0.95, probs['draw'])),
            'away': max(0.05, min(0.95, probs['away'])),
            'goal_probs': probs['goal_probs'],
            'home_lambda': home_lambda,
            'away_lambda': away_lambda,
        }


def completed_matches(session: Session) -> list:
    return session.exec(
        select(FootballMatch).where(FootballMatch.home_score.is_not(None))
    ).all()


def selection_is_under(context: dict) -> bool:
    return (context.get('selection') or '').lower() in ('under', 'menos')


def invert_for_under(prob: float, context: dict) -> float:
    return 1.0 - prob if selection_is_under(context) else prob


def team_ids(context: dict) -> set[int]:
    ids = set()
    for key in ('home_team_id', 'away_team_id'):
        value = context.get(key)
        if value:
            ids.add(value)
    return ids


def make_result(prob: float, coverage: str, sample_size: int, explanation: str) -> dict:
    return {
        'probability': max(0.05, min(0.95, prob)),
        'coverage_status': coverage,
        'sample_size': sample_size,
        'explanation': explanation,
    }


def estimate(session: Session, market_code: str, odds_decimal: float, context: dict):
    context = context or {}
    matches = completed_matches(session)
    ids = team_ids(context)

    if market_code in ESTIMATED_ONLY:
        return {'probability': None, 'coverage_status': 'estimated_only', 'sample_size': 0,
                'explanation': 'Mercado sin datos estadisticos suficientes'}

    if not ids:
        return None

    # Fit Poisson model
    model = PoissonModel(matches)
    home_id = context.get('home_team_id')
    away_id = context.get('away_team_id')

    if not home_id or not away_id:
        return None

    predict = model.predict_match(home_id, away_id)

    if market_code == 'match_winner':
        sel = (context.get('selection') or '').lower()
        prob_map = {'home': predict['home'], 'away': predict['away'], 'draw': predict['draw']}
        if sel in prob_map:
            return make_result(prob_map[sel], 'model' if model.sample_size >= 20 else 'heuristic',
                               model.sample_size,
                               f'Poisson 1X2: home_lambda={predict["home_lambda"]:.2f}, away_lambda={predict["away_lambda"]:.2f}, muestra={model.sample_size}')

    if market_code == 'total_goals_over_under':
        line = context.get('line')
        if line is not None:
            prob_over = sum(p for g, p in predict['goal_probs'].items() if g > line)
            prob = invert_for_under(prob_over, context)
            return make_result(prob, 'model' if model.sample_size >= 20 else 'heuristic',
                               model.sample_size,
                               f'Poisson total goles >{line}: {len(predict["goal_probs"])} escenarios, muestra={model.sample_size}')

    if market_code == 'both_teams_to_score':
        # BTTS probability = 1 - P(both score 0)
        # Using Poisson: P(home=0)*P(away=0)
        p_no_score = _poisson_prob(predict['home_lambda'], 0) * _poisson_prob(predict['away_lambda'], 0)
        prob_btts = 1.0 - p_no_score
        prob = 1.0 - prob_btts if (context.get('selection') or '').lower() == 'no' else prob_btts
        return make_result(prob, 'model' if model.sample_size >= 20 else 'heuristic',
                           model.sample_size,
                           f'BTTS via Poisson: {len(predict["goal_probs"])} escenarios, muestra={model.sample_size}')

    if market_code == 'team_goals_over_under':
        line = context.get('line')
        if line is not None:
            sel = (context.get('selection') or '').lower()
            team_lambda = predict['home_lambda'] if sel in ('home', 'equipo a', 'local') else predict['away_lambda']
            prob_over = 1.0 - sum(_poisson_prob(team_lambda, k) for k in range(int(line) + 1))
            prob = invert_for_under(prob_over, context)
            return make_result(prob, 'model' if model.sample_size >= 20 else 'heuristic',
                               model.sample_size,
                               f'Poisson goles equipo >{line}: lambda={team_lambda:.2f}, muestra={model.sample_size}')

    if market_code == 'double_chance':
        sel = (context.get('selection') or '').lower()
        values = {
            '1x': predict['home'] + predict['draw'],
            'x2': predict['draw'] + predict['away'],
            '12': predict['home'] + predict['away'],
        }
        if sel in values:
            return make_result(values[sel], 'model' if model.sample_size >= 20 else 'heuristic',
                               model.sample_size,
                               f'Doble oportunidad Poisson: muestra={model.sample_size}')

    return None
