"""Strict no-vig validation for one canonical market group."""
from __future__ import annotations


def calculate(sport: str, market_code: str | None, outcomes: list[dict]) -> tuple[list[float | None], str | None]:
    code = (market_code or "").lower()
    expected = 3 if code in {"match_winner", "1x2"} else 2 if code in {"total_goals_over_under", "over_under", "double_chance"} else None
    if sport != "football":
        return [None] * len(outcomes), "No disponible: no-vig LoL requiere validación específica."
    if expected is None:
        return [None] * len(outcomes), "No disponible: tipo de mercado no compatible."
    if len(outcomes) != expected:
        return [None] * len(outcomes), "No disponible: outcomes incompletos o incompatibles."
    total = sum(1 / item["odds_decimal"] for item in outcomes if item.get("odds_decimal"))
    if total <= 0:
        return [None] * len(outcomes), "No disponible: cuotas inválidas."
    return [round((1 / item["odds_decimal"]) / total, 4) for item in outcomes], None
