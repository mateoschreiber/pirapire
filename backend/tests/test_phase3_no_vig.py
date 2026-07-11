from app.services.no_vig import calculate


def test_1x2_normalizes_to_one():
    values, reason = calculate("football", "match_winner", [{"odds_decimal": 2.0}, {"odds_decimal": 3.0}, {"odds_decimal": 4.0}])
    assert reason is None
    assert round(sum(values), 4) == 1.0


def test_over_under_normalizes_to_one():
    values, reason = calculate("football", "over_under", [{"odds_decimal": 1.8}, {"odds_decimal": 2.1}])
    assert reason is None
    assert round(sum(values), 4) == 1.0


def test_incomplete_and_lol_are_unavailable():
    values, reason = calculate("football", "match_winner", [{"odds_decimal": 2.0}, {"odds_decimal": 3.0}])
    assert values == [None, None] and reason
    values, reason = calculate("lol", "map_winner", [{"odds_decimal": 2.0}, {"odds_decimal": 2.0}])
    assert values == [None, None] and reason


def test_distinct_market_groups_cannot_mix():
    first, _ = calculate("football", "over_under", [{"odds_decimal": 1.8}, {"odds_decimal": 2.0}])
    second, _ = calculate("football", "over_under", [{"odds_decimal": 1.7}, {"odds_decimal": 2.2}])
    assert round(sum(first), 4) == round(sum(second), 4) == 1.0
