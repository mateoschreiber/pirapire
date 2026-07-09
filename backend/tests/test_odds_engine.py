import math

import pytest

from app.services import combo_engine, odds_engine


def test_decimal_to_implied_probability():
    assert odds_engine.decimal_to_implied_probability(2.0) == 0.5
    assert math.isclose(odds_engine.decimal_to_implied_probability(4.0), 0.25)


def test_fair_odds():
    assert odds_engine.fair_odds(0.5) == 2.0
    assert odds_engine.fair_odds(0.25) == 4.0


def test_expected_value_break_even():
    assert math.isclose(odds_engine.expected_value(0.5, 2.0, 1.0), 0.0, abs_tol=1e-9)


def test_expected_value_positive_and_negative():
    assert odds_engine.expected_value(0.6, 2.0, 1.0) > 0
    assert odds_engine.expected_value(0.4, 2.0, 1.0) < 0


def test_risk_label():
    assert odds_engine.risk_label(0.70) == "low"
    assert odds_engine.risk_label(0.50) == "medium"
    assert odds_engine.risk_label(0.20) == "high"


def test_odds_engine_invalid_inputs():
    with pytest.raises(ValueError):
        odds_engine.decimal_to_implied_probability(0)
    with pytest.raises(ValueError):
        odds_engine.fair_odds(0)


def test_calculate_naive_combo_probability():
    assert combo_engine.calculate_naive_combo_probability([0.5, 0.5]) == 0.25
    assert math.isclose(
        combo_engine.calculate_naive_combo_probability([0.5, 0.5, 0.5]), 0.125
    )


def test_combo_fair_odds():
    assert combo_engine.calculate_combo_fair_odds(0.25) == 4.0


def test_combo_expected_value_break_even():
    assert math.isclose(
        combo_engine.calculate_combo_expected_value(0.25, 4.0, 1.0), 0.0, abs_tol=1e-9
    )


def test_combo_invalid_inputs():
    with pytest.raises(ValueError):
        combo_engine.calculate_naive_combo_probability([])
    with pytest.raises(ValueError):
        combo_engine.calculate_naive_combo_probability([1.2])
