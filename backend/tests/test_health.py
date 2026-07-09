from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_root():
    response = client.get("/")
    assert response.status_code == 200
    body = response.json()
    assert body["health"] == "/health"
    assert body["docs"] == "/docs"


def test_odds_analyze_endpoint():
    response = client.post("/odds/analyze", json={"odds_decimal": 2.0})
    assert response.status_code == 200
    data = response.json()
    assert data["implied_probability"] == 0.5
    assert data["fair_odds"] == 2.0


def test_combo_analyze_endpoint():
    response = client.post(
        "/combo/analyze",
        json={"legs": [{"probability": 0.5}, {"probability": 0.5}]},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["combo_probability"] == 0.25
    assert data["combo_fair_odds"] == 4.0
