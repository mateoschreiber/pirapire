"""Corrected Poisson football model — Phase 1."""
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
    """Exponential time decay."""
    if match_date is None:
        return 0.3
    if isinstance(match_date, str):
        try:
            match_date = datetime.fromisoformat(match_date.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            return 0.3
    if not isinstance(match_date, datetime):
        return 0.3
    days = max(0, (ref_date.replace(tzinfo=None) - match_date.replace(tzinfo=None)).days)
    return math.pow(2.0, -days / half_life_days)


def _poisson_pmf(lmbda: float, k: int) -> float:
    if lmbda <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lmbda) * (lmbda ** k) / math.factorial(k)


def _shrinkage(team_value: float, league_value: float, sample_weight: float, min_samples: int = 10) -> float:
    """Bayesian shrinkage toward league average for small samples."""
    alpha = min(1.0, sample_weight / max(min_samples, 1))
    return alpha * team_value + (1.0 - alpha) * league_value


class CorrectedPoissonModel:
    """Poisson model with proper team filtering, weighted ratings, shrinkage, and Dixon-Coles."""

    def __init__(self, matches: list, home_id: int | None = None, away_id: int | None = None,
                 ref_date: datetime | None = None):
        self.ref_date = ref_date or datetime.utcnow()
        self.home_id = home_id
        self.away_id = away_id

        # Per-team stats: total weighted goals for/against, total weight
        self.team_goals_for = defaultdict(float)
        self.team_goals_against = defaultdict(float)
        self.team_weight_attack = defaultdict(float)
        self.team_weight_defense = defaultdict(float)
        self.home_advantage = 0.0
        self.league_avg_goals = 1.35

        # Sample sizes per team
        self.home_sample = 0
        self.away_sample = 0
        self.total_sample = 0
        self.competition_sample = 0

        self.rho = -0.06  # Dixon-Coles low-score correlation

        self._fit(matches)

    def _fit(self, matches: list):
        valid = []
        for m in matches:
            if m.home_score is None or m.away_score is None:
                continue
            if m.home_team_id is None or m.away_team_id is None:
                continue
            w = _decay_weight(m.start_time, self.ref_date)
            valid.append((m, w))

        if not valid:
            return

        self.total_sample = len(valid)

        # Team-specific stats
        for m, w in valid:
            # Home team: scored home_score, conceded away_score
            self.team_goals_for[m.home_team_id] += (m.home_score or 0) * w
            self.team_goals_against[m.home_team_id] += (m.away_score or 0) * w
            self.team_weight_attack[m.home_team_id] += w
            self.team_weight_defense[m.home_team_id] += w

            # Away team: scored away_score, conceded home_score
            self.team_goals_for[m.away_team_id] += (m.away_score or 0) * w
            self.team_goals_against[m.away_team_id] += (m.home_score or 0) * w
            self.team_weight_attack[m.away_team_id] += w
            self.team_weight_defense[m.away_team_id] += w

        # Home advantage
        hg = sum((m.home_score or 0) * w for m, w in valid)
        ag = sum((m.away_score or 0) * w for m, w in valid)
        total_w = sum(w for _, w in valid)
        if total_w > 0:
            avg_home = hg / total_w if total_w > 0 else 0
            avg_away = ag / total_w if total_w > 0 else 0
            self.league_avg_goals = max(0.5, (hg + ag) / (2 * total_w)) if total_w > 0 else 1.35
            self.home_advantage = max(0.0, avg_home - avg_away)

        # Sample sizes for the specific matchup
        if self.home_id:
            self.home_sample = int(self.team_weight_attack.get(self.home_id, 0))
        if self.away_id:
            self.away_sample = int(self.team_weight_attack.get(self.away_id, 0))

    def _team_attack_rating(self, team_id: int | None) -> float:
        if team_id is None:
            return 1.0
        gf = self.team_goals_for.get(team_id, 0)
        tw = self.team_weight_attack.get(team_id, 0)
        if tw <= 0:
            return 1.0
        raw = gf / tw
        avg = self.league_avg_goals
        return _shrinkage(raw / max(avg, 0.5), 1.0, tw)

    def _team_defense_rating(self, team_id: int | None) -> float:
        if team_id is None:
            return 1.0
        ga = self.team_goals_against.get(team_id, 0)
        tw = self.team_weight_defense.get(team_id, 0)
        if tw <= 0:
            return 1.0
        raw = ga / tw
        avg = self.league_avg_goals
        return _shrinkage(raw / max(avg, 0.5), 1.0, tw)

    def predict_match(self, home_id: int, away_id: int) -> dict:
        home_atk = self._team_attack_rating(home_id)
        home_def = self._team_defense_rating(home_id)
        away_atk = self._team_attack_rating(away_id)
        away_def = self._team_defense_rating(away_id)

        home_lambda = max(0.10, self.league_avg_goals * home_atk * away_def + self.home_advantage * 0.4)
        away_lambda = max(0.10, self.league_avg_goals * away_atk * home_def)

        max_g = 12
        probs = [[0.0] * (max_g + 1) for _ in range(max_g + 1)]
        for i in range(max_g + 1):
            for j in range(max_g + 1):
                probs[i][j] = _poisson_pmf(home_lambda, i) * _poisson_pmf(away_lambda, j)

        # Dixon-Coles adjustment for 0-0, 1-0, 0-1, 1-1
        rho = self.rho
        if abs(rho) > 1e-9:
            for i in range(2):
                for j in range(2):
                    p = _poisson_pmf(home_lambda, i) * _poisson_pmf(away_lambda, j)
                    if i == 0 and j == 0:
                        adj = p * (1.0 + home_lambda * away_lambda * rho)
                    elif i == 0 and j == 1:
                        adj = p * (1.0 - home_lambda * rho)
                    elif i == 1 and j == 0:
                        adj = p * (1.0 - away_lambda * rho)
                    elif i == 1 and j == 1:
                        adj = p * (1.0 + rho)
                    else:
                        adj = p
                    probs[i][j] = max(0.0, adj)

        # Normalize
        total_p = sum(sum(row) for row in probs)
        if total_p > 0:
            for i in range(max_g + 1):
                for j in range(max_g + 1):
                    probs[i][j] /= total_p

        # Calculate outcome probabilities
        home_win = sum(probs[i][j] for i in range(max_g + 1) for j in range(max_g + 1) if i > j)
        away_win = sum(probs[i][j] for i in range(max_g + 1) for j in range(max_g + 1) if i < j)
        draw = sum(probs[i][j] for i in range(max_g + 1) for j in range(max_g + 1) if i == j)

        # Goal total probabilities
        goal_probs = defaultdict(float)
        for i in range(max_g + 1):
            for j in range(max_g + 1):
                goal_probs[i + j] += probs[i][j]

        return {
            'home': home_win,
            'draw': draw,
            'away': away_win,
            'goal_probs': dict(goal_probs),
            'home_lambda': round(home_lambda, 3),
            'away_lambda': round(away_lambda, 3),
        }

    @property
    def effective_sample(self) -> int:
        return max(self.home_sample, self.away_sample)


def completed_matches(session: Session) -> list:
    return session.exec(
        select(FootballMatch).where(FootballMatch.home_score.is_not(None))
    ).all()


def team_ids(context: dict) -> set[int]:
    ids = set()
    for key in ('home_team_id', 'away_team_id'):
        v = context.get(key)
        if v:
            ids.add(v)
    return ids


def make_result(prob: float, coverage: str, sample_size: int, model, explanation: str) -> dict:
    return {
        'probability': prob,
        'coverage_status': coverage,
        'sample_size': sample_size,
        'model_confidence': round(min(1.0, sample_size / 30.0), 3) if sample_size > 0 else 0.0,
        'explanation': explanation,
    }


def selection_is_under(context: dict) -> bool:
    return (context.get('selection') or '').lower() in ('under', 'menos')


def estimate(session: Session, market_code: str, odds_decimal: float, context: dict):
    context = context or {}

    if market_code in ESTIMATED_ONLY:
        return {'probability': None, 'coverage_status': 'insufficient_data', 'sample_size': 0,
                'model_confidence': 0.0, 'explanation': 'Mercado sin datos estadisticos'}

    home_id = context.get('home_team_id')
    away_id = context.get('away_team_id')
    if not home_id or not away_id:
        return None

    matches = completed_matches(session)
    model = CorrectedPoissonModel(matches, home_id, away_id)

    if model.effective_sample < 3:
        return {'probability': None, 'coverage_status': 'insufficient_data', 'sample_size': model.effective_sample,
                'model_confidence': 0.0, 'explanation': f'Muestra insuficiente: {model.effective_sample} partidos'}

    pred = model.predict_match(home_id, away_id)
    sample = model.effective_sample
    coverage = 'model' if sample >= 30 else 'heuristic'

    if market_code == 'match_winner':
        sel = (context.get('selection') or '').lower()
        prob_map = {'home': pred['home'], 'away': pred['away'], 'draw': pred['draw']}
        if sel in prob_map:
            return make_result(prob_map[sel], coverage, sample, model,
                f'Poisson 1X2: home={pred["home_lambda"]} away={pred["away_lambda"]}, muestra={sample}')

    if market_code == 'total_goals_over_under':
        line = context.get('line')
        if line is not None:
            prob_over = sum(p for g, p in pred['goal_probs'].items() if g > line)
            prob = 1.0 - prob_over if selection_is_under(context) else prob_over
            return make_result(prob, coverage, sample, model,
                f'Poisson >{line} goles: home_lambda={pred["home_lambda"]} away_lambda={pred["away_lambda"]}, muestra={sample}')

    if market_code == 'both_teams_to_score':
        # P(BTTS) = P(home>0 AND away>0) = sum over i>0,j>0 of P(i,j)
        btts = 0.0
        for g, p in pred['goal_probs'].items():
            btts += p  # This is wrong - need proper joint probability
        # Correct BTTS: P(home>0 AND away>0) = 1 - P(home=0) - P(away=0) + P(home=0,away=0)
        p_h0 = _poisson_pmf(pred['home_lambda'], 0)
        p_a0 = _poisson_pmf(pred['away_lambda'], 0)
        p_00 = p_h0 * p_a0  # independence assumption for Poisson
        btts_correct = 1.0 - p_h0 - p_a0 + p_00
        prob = 1.0 - btts_correct if (context.get('selection') or '').lower() == 'no' else btts_correct
        return make_result(max(0.02, min(0.98, prob)), coverage, sample, model,
            f'BTTS: home_lambda={pred["home_lambda"]} away_lambda={pred["away_lambda"]}, muestra={sample}')

    if market_code == 'team_goals_over_under':
        line = context.get('line')
        if line is not None:
            sel = (context.get('selection') or '').lower()
            team_lambda = pred['home_lambda'] if sel in ('home', 'equipo a', 'local') else pred['away_lambda']
            prob_over = 1.0 - sum(_poisson_pmf(team_lambda, k) for k in range(int(line) + 1))
            prob = 1.0 - prob_over if selection_is_under(context) else prob_over
            return make_result(max(0.02, min(0.98, prob)), coverage, sample, model,
                f'Goles equipo >{line}: lambda={team_lambda:.2f}, muestra={sample}')

    if market_code == 'double_chance':
        sel = (context.get('selection') or '').lower()
        values = {'1x': pred['home'] + pred['draw'], 'x2': pred['draw'] + pred['away'],
                  '12': pred['home'] + pred['away']}
        if sel in values:
            return make_result(max(0.02, min(0.98, values[sel])), coverage, sample, model,
                f'Doble oportunidad Poisson, muestra={sample}')

    return None
