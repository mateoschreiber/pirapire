"""Build combo (parlay) recommendations from ranked single bets."""

from itertools import combinations

from . import ranking

CORRELATION_BASE = 0.97


def _distinct_markets(legs: list) -> bool:
    """No two legs share the exact same market on the same event."""
    seen = set()
    for leg in legs:
        key = (leg.get("event_label"), leg.get("market_code"), leg.get("line"))
        if key in seen:
            return False
        seen.add(key)
    return True


def _distinct_events(legs: list) -> bool:
    events = [leg.get("event_label") for leg in legs]
    return len(set(events)) == len(events)


def build(
    singles: list,
    mode: str,
    max_legs: int = 3,
    max_combos: int = 20,
    max_pool: int = 8,
) -> list:
    """Generate combos of size 2..max_legs from the strongest singles.

    Legs must come from distinct events (avoids correlated same-match markets).
    """
    pool = singles[:max_pool]
    combos = []
    max_legs = max(2, min(max_legs, 5))

    for size in range(2, max_legs + 1):
        for combo_legs in combinations(pool, size):
            legs = list(combo_legs)
            if not _distinct_events(legs) or not _distinct_markets(legs):
                continue

            offered = 1.0
            prob = 1.0
            for leg in legs:
                offered *= leg.get("odds_decimal", 1.0)
                prob *= leg.get("model_probability", 0.0)
            # mild correlation penalty as legs grow
            prob *= CORRELATION_BASE ** (size - 1)
            prob = max(0.0001, min(0.999, prob))

            fair = 1.0 / prob if prob > 0 else 0.0
            ev = prob * (offered - 1.0) - (1.0 - prob)

            worst_risk = _worst_risk(legs)
            combo = {
                "legs": legs,
                "legs_count": size,
                "sport": legs[0].get("sport"),
                "offered_odds": offered,
                "model_probability": prob,
                "implied_probability": (1.0 / offered) if offered else 0.0,
                "fair_odds": fair,
                "expected_value": ev,
                "odds_decimal": offered,
                "risk_label": worst_risk,
            }
            combos.append(combo)

    ranked = ranking.rank(combos, mode)
    return ranked[:max_combos]


_RISK_ORDER = ["low", "medium", "high", "very_high"]


def _worst_risk(legs: list) -> str:
    worst = 0
    for leg in legs:
        label = leg.get("risk_label") or "medium"
        if label in _RISK_ORDER:
            worst = max(worst, _RISK_ORDER.index(label))
    return _RISK_ORDER[worst]
