import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_dashboard_html():
    r = client.get("/")
    assert r.status_code == 200
    assert "Pirapire" in r.text
    assert "Proximos encuentros" in r.text


def test_match_detail_html():
    r = client.get("/lol/matches/test123")
    assert r.status_code == 200
    assert "Cargando" in r.text


def test_upcoming_api():
    r = client.get("/api/lol/matches/upcoming?hours=48")
    assert r.status_code == 200
    data = r.json()
    assert "matches" in data
    assert "count" in data
    assert data["window_hours"] == 48


def test_upcoming_timezone():
    r = client.get("/api/lol/matches/upcoming")
    assert r.json()["timezone"] == "America/Asuncion"


def test_match_not_found():
    r = client.get("/api/lol/matches/nonexistent_key_xyz")
    assert r.status_code == 404


def test_static_css():
    r = client.get("/static/css/styles.css")
    assert r.status_code == 200


def test_static_js():
    r = client.get("/static/js/app.js")
    assert r.status_code == 200


def test_js_no_legacy_keywords():
    r = client.get("/static/js/app.js")
    assert r.status_code == 200
    text = r.text.lower()
    assert "aposta" not in text
    assert "kambi" not in text
    assert "football" not in text
    assert "sofascore" not in text
