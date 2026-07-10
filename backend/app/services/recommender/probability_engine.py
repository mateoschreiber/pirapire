from sqlmodel import Session

from ..features import football_features, lol_features


def clamp(value: float, low: float = 0.03, high: float = 0.97) -> float:
    return max(low, min(high, value))


def estimate(session: Session, sport: str, market_code: str, odds_decimal: float, context: dict = None) -> dict:
    context = context or {}
    implied = (1.0 / odds_decimal) if odds_decimal and odds_decimal > 0 else 0.0
    data_probability = None
    coverage = None
    sample_size = 0
    explanation = None
    raw_confidence = None

    if market_code:
        if sport == 'football':
            raw = football_features.estimate(session, market_code, odds_decimal, context)
        elif sport == 'lol':
            raw = lol_features.estimate(session, market_code, odds_decimal, context)
        else:
            raw = None
        if isinstance(raw, dict):
            data_probability = raw.get('probability')
            coverage = raw.get('coverage_status')
            sample_size = raw.get('sample_size') or 0
            explanation = raw.get('explanation')
            raw_confidence = raw.get('model_confidence')
        elif raw:
            data_probability, coverage = raw
    else:
        coverage = 'unsupported'

    match_confidence = context.get('match_confidence') or 0.0

    if data_probability is None:
        model = None
        coverage = 'insufficient_data'
        data_weight = 0.0
    else:
        model = data_probability
        coverage = coverage or 'model'
        data_weight = min(1.0, (sample_size / 20.0) if sample_size else 0.35)
        if match_confidence and match_confidence < 0.50:
            coverage = 'insufficient_data'
            model = None
            data_weight = 0.0
        elif match_confidence and match_confidence < 0.70:
            coverage = 'estimated_only'

    if model is None:
        return {
            'model_probability': None,
            'implied_probability': implied,
            'fair_odds': None,
            'expected_value': None,
            'edge': None,
            'coverage_status': 'insufficient_data',
            'model_confidence': 0.0,
            'sample_size': 0,
            'explanation': explanation or 'Datos insuficientes para generar prediccion estadistica',
        }

    model = clamp(model)
    fair = 1.0 / model if model > 0 else 0.0
    ev = model * odds_decimal - 1.0 if odds_decimal else 0.0
    edge = model - implied
    if explanation is None:
        explanation = '%s: prob modelo %.1f%%, edge %.1f%%' % (coverage, model * 100, edge * 100)

    return {
        'model_probability': model,
        'implied_probability': implied,
        'fair_odds': fair,
        'expected_value': ev,
        'edge': edge,
        'coverage_status': coverage or 'model',
        'model_confidence': round(data_weight, 3),
        'sample_size': sample_size,
        'explanation': explanation,
    }