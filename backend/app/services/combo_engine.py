"""Pure functions to analyze naive combined (parlay) bets."""

from collections.abc import Iterable
from functools import reduce


def calculate_naive_combo_probability(probabilities: Iterable[float]) -> float:
    """Multiply independent leg probabilities into a combined probability."""
    probs = list(probabilities)
    if not probs:
        raise ValueError("probabilities must not be empty")
    for p in probs:
        if not 0 <= p <= 1:
            raise ValueError("each probability must be in the [0, 1] range")
    return reduce(lambda a, b: a * b, probs, 1.0)


def calculate_combo_fair_odds(probability: float) -> float:
    """Return the break-even decimal odds for a combined probability."""
    if not 0 < probability <= 1:
        raise ValueError("probability must be in the (0, 1] range")
    return 1.0 / probability


def calculate_combo_expected_value(
    probability: float, offered_odds: float, stake: float = 1.0
) -> float:
    """Expected value of a combined bet at the offered decimal odds."""
    if not 0 <= probability <= 1:
        raise ValueError("probability must be in the [0, 1] range")
    if offered_odds <= 0:
        raise ValueError("offered_odds must be greater than 0")
    return (probability * (offered_odds - 1.0) - (1.0 - probability)) * stake
