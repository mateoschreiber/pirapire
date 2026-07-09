"""Pure functions to analyze single decimal odds."""


def decimal_to_implied_probability(odds: float) -> float:
    """Convert decimal odds into the implied probability (1 / odds)."""
    if odds <= 0:
        raise ValueError("odds must be greater than 0")
    return 1.0 / odds


def fair_odds(probability: float) -> float:
    """Return the break-even (fair) decimal odds for a probability."""
    if not 0 < probability <= 1:
        raise ValueError("probability must be in the (0, 1] range")
    return 1.0 / probability


def expected_value(probability: float, odds: float, stake: float = 1.0) -> float:
    """Expected value of a bet given a probability, decimal odds and stake."""
    if not 0 <= probability <= 1:
        raise ValueError("probability must be in the [0, 1] range")
    if odds <= 0:
        raise ValueError("odds must be greater than 0")
    return (probability * (odds - 1.0) - (1.0 - probability)) * stake


def risk_label(probability: float) -> str:
    """Classify a probability into a qualitative risk bucket."""
    if not 0 <= probability <= 1:
        raise ValueError("probability must be in the [0, 1] range")
    if probability >= 0.65:
        return "low"
    if probability >= 0.40:
        return "medium"
    return "high"
