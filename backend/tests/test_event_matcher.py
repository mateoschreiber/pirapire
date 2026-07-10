import pytest

from app.services.text_normalizer import normalize


def test_normalize_lowercase():
    assert normalize("Real Madrid CF") == "real madrid"
    assert normalize("TEAM") == ""


def test_normalize_accents():
    result = normalize("Atletico Madrid")
    assert "atletico" in result


def test_normalize_special_chars():
    result = normalize("Team-eSports!")
    assert "esports" not in result
    assert "team" not in result


def test_normalize_empty():
    assert normalize("") == ""
    assert normalize(None) == ""


def test_normalize_whitespace():
    assert normalize("  Real   Madrid  ") == "real madrid"


def test_normalize_team_removal():
    assert normalize("Team Liquid") == "liquid"
    assert normalize("T1") == "t1"


def test_normalize_fc_removal():
    assert normalize("FC Barcelona") == "barcelona"
