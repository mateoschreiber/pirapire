from sqlmodel import Session

from ...config import settings
from .. import lol_metrics_engine


def finish(prob, coverage, sample_size, confidence, explanation):
    if prob is None:
        return {'probability': None, 'coverage_status': coverage, 'sample_size': sample_size or 0, 'explanation': explanation}
    return {
        'probability': max(0.05, min(0.95, prob)),
        'coverage_status': coverage,
        'sample_size': sample_size or 0,
        'model_confidence': confidence,
        'explanation': explanation,
    }


def coverage_for(sample_size: int, confidence: float) -> str:
    if sample_size >= settings.lol_history_min_games_team and confidence >= 0.45:
        return 'model'
    if sample_size > 0:
        return 'estimated_only'
    return 'odds_implied_only'


def estimate(session: Session, market_code: str, odds_decimal: float, context: dict):
    context = context or {}
    line = context.get('line')
    selection = context.get('selection')
    league = context.get('league')
    team_a = context.get('lol_team_name') or context.get('team_a')
    team_b = context.get('lol_opponent_name') or context.get('team_b')
    window = getattr(settings, 'lol_history_recent_games_window', 20)

    matchup = None
    if team_a and team_b:
        matchup = lol_metrics_engine.matchup_metrics(session, team_a, team_b, league, window)

    if market_code in ('map_winner', 'series_winner'):
        if not matchup:
            return finish(None, 'odds_implied_only', 0, 0, 'Sin historial LoL suficiente para ganador')
        a = matchup['team_a']
        b = matchup['team_b']
        sample = matchup['sample_size']
        conf = matchup['confidence']
        awr = a.get('winrate')
        bwr = b.get('winrate')
        if awr is None or bwr is None or sample == 0:
            return finish(None, 'odds_implied_only', sample, conf, 'Sin winrate historico suficiente')
        total = max(0.01, awr + bwr)
        prob_a = awr / total
        sel = (selection or '').lower()
        prob = prob_a if sel in ('home', 'team_a', '1') else 1.0 - prob_a
        return finish(prob, coverage_for(sample, conf), sample, conf, 'Winrate reciente LoL: %s vs %s, muestra %s' % (team_a, team_b, sample))

    metric_map = {
        'total_kills_over_under': 'avg_combined_kills',
        'total_towers_over_under': 'avg_towers_total',
        'total_inhibitors_over_under': 'avg_inhibitors_total',
        'dragons_over_under': 'avg_dragons_total',
        'barons_over_under': 'avg_barons_total',
        'game_duration_over_under': 'avg_game_duration_seconds',
    }
    if market_code in metric_map:
        if not matchup:
            return finish(None, 'odds_implied_only', 0, 0, 'Sin matchup historico LoL')
        mean_value = matchup.get(metric_map[market_code])
        prob = lol_metrics_engine.probability_over_under(mean_value, line, selection)
        sample = matchup['sample_size']
        conf = matchup['confidence']
        return finish(prob, coverage_for(sample, conf), sample, conf, '%s promedio %.2f vs linea %s' % (market_code, mean_value or 0, line))

    if market_code in ('team_kills_over_under', 'team_towers_over_under', 'team_inhibitors_over_under'):
        if not matchup:
            return finish(None, 'odds_implied_only', 0, 0, 'Sin historial del equipo')
        side = matchup['team_a'] if (selection or '').lower() not in ('away', 'team_b') else matchup['team_b']
        field = 'avg_kills' if 'kills' in market_code else ('avg_towers' if 'towers' in market_code else 'avg_inhibitors')
        mean_value = side.get(field)
        prob = lol_metrics_engine.probability_over_under(mean_value, line, selection)
        sample = side['sample_size']
        conf = side['confidence']
        return finish(prob, coverage_for(sample, conf), sample, conf, '%s del equipo promedio %.2f vs linea %s' % (field, mean_value or 0, line))

    if market_code in ('player_kills_over_under', 'player_deaths_over_under'):
        player = context.get('player')
        role = context.get('role')
        if not player:
            return finish(None, 'estimated_only', 0, 0, 'Mercado de jugador sin nombre detectable')
        metrics = lol_metrics_engine.player_metrics(session, player, role, league, window)
        field = 'avg_kills' if 'kills' in market_code else 'avg_deaths'
        mean_value = metrics.get(field)
        prob = lol_metrics_engine.probability_over_under(mean_value, line, selection)
        sample = metrics['sample_size']
        conf = metrics['confidence']
        coverage = 'model' if sample >= settings.lol_history_min_games_player else ('estimated_only' if sample else 'odds_implied_only')
        return finish(prob, coverage, sample, conf, '%s de jugador promedio %.2f vs linea %s' % (field, mean_value or 0, line))

    return finish(None, 'unsupported', 0, 0, 'Mercado LoL no soportado por historial')
