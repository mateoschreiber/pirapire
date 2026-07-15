from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_api_info():
    response = client.get("/api/info")
    assert response.status_code == 200
    data = response.json()
    assert data["app"] == "Pirapire"
    assert data["health"] == "/health"
    assert data["docs"] == "/docs"


def test_docs():
    assert client.get("/docs").status_code == 200


def test_odds_analyze_endpoint():
    response = client.post("/odds/analyze", json={"odds_decimal": 2.0})
    assert response.status_code == 200
    assert response.json()["implied_probability"] == 0.5


def test_combo_analyze_endpoint():
    response = client.post(
        "/combo/analyze",
        json={"legs": [{"probability": 0.5}, {"probability": 0.5}]},
    )
    assert response.status_code == 200
    assert response.json()["combo_probability"] == 0.25
