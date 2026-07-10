from itertools import combinations

from . import ranking

CORRELATION_BASE = 0.97


def distinct_events(legs: list) -> bool:
    events = [leg.get('event_key') or leg.get('event_label') for leg in legs]
    return len(set(events)) == len(events)


def distinct_markets(legs: list) -> bool:
    seen = set()
    for leg in legs:
        key = (leg.get('event_key') or leg.get('event_label'), leg.get('market_code'), leg.get('line'))
        if key in seen:
            return False
        seen.add(key)
    return True


def correlation_ok(legs: list) -> bool:
    team_markets = set()
    for leg in legs:
        key = (leg.get('event_key') or leg.get('event_label'), leg.get('selection_text'), leg.get('market_code'))
        if key in team_markets:
            return False
        team_markets.add(key)
    return True


def leg_explanation(legs: list) -> str:
    parts = []
    for leg in legs:
        parts.append('%s: P %.1f%%, EV %.2f' % (
            leg.get('event_label') or '',
            (leg.get('model_probability') or 0.0) * 100,
            leg.get('expected_value') or 0.0,
        ))
    return '; '.join(parts)


def build(singles: list, mode: str, max_legs: int = 3, max_combos: int = 20, max_pool: int = 10, max_combo_odds: float = None) -> list:
    pool = singles[:max_pool]
    combos = []
    max_legs = max(2, min(max_legs or 3, 5))

    for size in range(2, max_legs + 1):
        for combo_legs in combinations(pool, size):
            legs = list(combo_legs)
            if not distinct_events(legs) or not distinct_markets(legs) or not correlation_ok(legs):
                continue
            offered = 1.0
            prob = 1.0
            for leg in legs:
                offered *= leg.get('odds_decimal', 1.0)
                prob *= leg.get('model_probability', 0.0)
            if max_combo_odds is not None and offered > max_combo_odds:
                continue
            prob *= CORRELATION_BASE ** (size - 1)
            prob = max(0.0001, min(0.999, prob))
            implied = 1.0 / offered if offered else 0.0
            fair = 1.0 / prob if prob > 0 else 0.0
            ev = prob * offered - 1.0
            combo = {
                'legs': legs,
                'legs_count': size,
                'sport': legs[0].get('sport'),
                'offered_odds': offered,
                'model_probability': prob,
                'implied_probability': implied,
                'fair_odds': fair,
                'expected_value': ev,
                'edge': prob - implied,
                'odds_decimal': offered,
                'risk_label': worst_risk(legs),
                'explanation': leg_explanation(legs),
            }
            if mode in ('profit', 'balanced') and combo['expected_value'] <= 0:
                continue
            combos.append(combo)

    ranked = ranking.rank(combos, mode)
    return ranked[:max_combos]


RISK_ORDER = ['low', 'medium', 'high', 'very_high']


def worst_risk(legs: list) -> str:
    worst = 0
    for leg in legs:
        label = leg.get('risk_label') or 'medium'
        if label in RISK_ORDER:
            worst = max(worst, RISK_ORDER.index(label))
    return RISK_ORDER[worst]
