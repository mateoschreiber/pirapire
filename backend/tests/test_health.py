from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs():
    assert client.get("/docs").status_code == 200


def test_sources_api():
    response = client.get("/api/sources")
    assert response.status_code == 200
    assert any(item["code"] == "oracles_elixir" for item in response.json()["sources"])


def test_removed_domains_stay_removed():
    assert client.post("/odds/analyze", json={"odds_decimal": 2.0}).status_code == 404
    assert client.post("/combo/analyze", json={"legs": []}).status_code == 404