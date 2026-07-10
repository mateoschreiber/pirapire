import pytest

from app.services.text_normalizer import normalize


def test_market_matcher_normalize():
    assert normalize("Ganador del partido") == "ganador del partido"
    assert normalize("Total de goles") == "total goles"


def test_market_text_normalized_no_accents():
    result = normalize("Mas de 2.5")
    assert "mas" in result


def test_normalize_handicap():
    result = normalize("Handicap -1.5")
    assert "handicap" in result


def test_normalize_selection_text():
    assert normalize("Over 2.5") == "over 2 5"
    assert normalize("Under 1.5") == "under 1 5"
