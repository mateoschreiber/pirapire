from sqlmodel import Session, select

from ...models_football import FootballMatch

ESTIMATED_ONLY = {
    'cards_over_under',
    'corners_over_under',
    'shots_on_target_over_under',
    'team_shots_on_target_over_under',
    'player_shots_on_target_over_under',
    'player_cards',
    'anytime_goalscorer',
}


def completed_matches(session: Session):
    return session.exec(select(FootballMatch).where(FootballMatch.home_score.is_not(None))).all()


def selection_is_under(context: dict) -> bool:
    return (context.get('selection') or '').lower() in ('under', 'menos')


def invert_for_under(prob: float, context: dict) -> float:
    return 1.0 - prob if selection_is_under(context) else prob


def result(prob: float, coverage: str, sample_size: int, explanation: str) -> dict:
    return {
        'probability': max(0.05, min(0.95, prob)),
        'coverage_status': coverage,
        'sample_size': sample_size,
        'explanation': explanation,
    }


def team_ids(context: dict) -> set[int]:
    ids = set()
    for key in ('home_team_id', 'away_team_id'):
        value = context.get(key)
        if value:
            ids.add(value)
    return ids


def recent_for_teams(matches, ids: set[int]):
    if not ids:
        return matches
    filtered = [m for m in matches if m.home_team_id in ids or m.away_team_id in ids]
    return filtered or matches


def estimate_match_winner(matches, context: dict):
    selection = (context.get('selection') or '').lower()
    home_id = context.get('home_team_id')
    away_id = context.get('away_team_id')
    if not home_id or not away_id:
        return None
    home_pts = away_pts = draws = sample = 0
    for m in matches:
        if m.home_score is None or m.away_score is None:
            continue
        if m.home_team_id == home_id or m.away_team_id == home_id:
            sample += 1
            home_pts += 1 if ((m.home_team_id == home_id and m.home_score > m.away_score) or (m.away_team_id == home_id and m.away_score > m.home_score)) else 0
            draws += 1 if m.home_score == m.away_score else 0
        if m.home_team_id == away_id or m.away_team_id == away_id:
            away_pts += 1 if ((m.home_team_id == away_id and m.home_score > m.away_score) or (m.away_team_id == away_id and m.away_score > m.home_score)) else 0
    if sample < 4:
        return None
    home_rate = home_pts / sample
    away_rate = away_pts / sample
    draw_rate = draws / max(1, sample)
    total = home_rate + away_rate + draw_rate or 1.0
    if selection == 'home':
        prob = home_rate / total
    elif selection == 'away':
        prob = away_rate / total
    elif selection == 'draw':
        prob = draw_rate / total
    else:
        return None
    return result(prob, 'heuristic', sample, f'Forma reciente 1X2 con {sample} partidos relacionados')


def estimate(session: Session, market_code: str, odds_decimal: float, context: dict):
    context = context or {}
    matches = completed_matches(session)
    ids = team_ids(context)
    related = recent_for_teams(matches, ids)

    if market_code == 'total_goals_over_under':
        line = context.get('line')
        if line is None:
            return None
        totals = [(m.home_score or 0) + (m.away_score or 0) for m in related if m.home_score is not None and m.away_score is not None]
        if len(totals) >= 5:
            prob = sum(1 for t in totals if t > line) / len(totals)
            prob = invert_for_under(prob, context)
            coverage = 'model' if ids else 'heuristic'
            return result(prob, coverage, len(totals), f'Total goles sobre linea {line} usando {len(totals)} partidos')
        return None

    if market_code == 'match_winner':
        return estimate_match_winner(related, context)

    if market_code == 'both_teams_to_score':
        usable = [m for m in related if m.home_score is not None and m.away_score is not None]
        if len(usable) >= 5:
            yes = sum(1 for m in usable if (m.home_score or 0) > 0 and (m.away_score or 0) > 0) / len(usable)
            prob = 1.0 - yes if (context.get('selection') or '').lower() == 'no' else yes
            return result(prob, 'heuristic', len(usable), f'Ambos anotan en {len(usable)} partidos recientes')
        return None

    if market_code == 'team_goals_over_under':
        line = context.get('line')
        if line is None or not ids:
            return None
        values = []
        for m in related:
            if m.home_score is None or m.away_score is None:
                continue
            if m.home_team_id in ids:
                values.append(m.home_score)
            if m.away_team_id in ids:
                values.append(m.away_score)
        if len(values) >= 5:
            prob = sum(1 for v in values if v > line) / len(values)
            prob = invert_for_under(prob, context)
            return result(prob, 'heuristic', len(values), f'Goles de equipo sobre linea {line} con {len(values)} muestras')
        return None

    if market_code == 'double_chance':
        mw = estimate_match_winner(related, {**context, 'selection': 'home'})
        draw = estimate_match_winner(related, {**context, 'selection': 'draw'})
        away = estimate_match_winner(related, {**context, 'selection': 'away'})
        if mw and draw and away:
            sel = (context.get('selection') or '').lower()
            values = {'1x': mw['probability'] + draw['probability'], '12': mw['probability'] + away['probability'], 'x2': draw['probability'] + away['probability']}
            if sel in values:
                return result(min(0.95, values[sel]), 'heuristic', mw['sample_size'], 'Doble oportunidad derivada del 1X2 estimado')
        return None

    if market_code in ESTIMATED_ONLY:
        return {'probability': None, 'coverage_status': 'estimated_only', 'sample_size': 0, 'explanation': 'Mercado sin datos suficientes'}
    return None
