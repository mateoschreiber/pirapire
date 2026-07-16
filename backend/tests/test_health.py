from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_docs():
    assert client.get("/docs").status_code == 200


def test_favicon_is_served():
    response = client.get("/favicon.ico")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/svg+xml"


def test_sources_api():
    response = client.get("/api/sources")
    assert response.status_code == 200
    assert any(item["code"] == "oracles_elixir" for item in response.json()["sources"])
    leaguepedia = next(item for item in response.json()["sources"] if item["code"] == "leaguepedia_schedule")
    assert leaguepedia["managed_by"] == "runtime"
    assert leaguepedia["configured"] is True
    assert leaguepedia["base_url"].endswith("/Special:CargoExport")


def test_removed_domains_stay_removed():
    assert client.post("/odds/analyze", json={"odds_decimal": 2.0}).status_code == 404
    assert client.post("/combo/analyze", json={"legs": []}).status_code == 404
