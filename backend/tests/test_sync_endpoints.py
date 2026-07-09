from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.routers import sources as sources_router

client = TestClient(app)


def _fake_result(*args, **kwargs):
    return {"inserted": 0, "updated": 0, "skipped": 0, "status": "success"}


def test_sync_football_returns_run_id(monkeypatch):
    monkeypatch.setattr(sources_router.football_sync, "sync", _fake_result)
    response = client.post("/sources/sync/football")
    assert response.status_code == 200
    body = response.json()
    assert "run_id" in body
    assert body["status"] in ("running", "success", "partial", "error")


def test_sync_lol_returns_run_id(monkeypatch):
    monkeypatch.setattr(sources_router.lol_sync, "sync", _fake_result)
    response = client.post("/sources/sync/lol")
    assert response.status_code == 200
    assert "run_id" in response.json()


def test_sync_all_returns_run_id(monkeypatch):
    monkeypatch.setattr(sources_router.sync_all, "sync", lambda session, run: _fake_result())
    response = client.post("/sources/sync/all")
    assert response.status_code == 200
    assert "run_id" in response.json()


def test_sync_by_slug(monkeypatch):
    monkeypatch.setattr(sources_router.football_sync, "sync", _fake_result)
    response = client.post("/sources/sync/football_data_org")
    assert response.status_code == 200
    assert response.json()["source_slug"] == "football_data_org"


def test_sync_by_slug_unknown_is_404():
    assert client.post("/sources/sync/not_a_source").status_code == 404


def test_source_runs_endpoint():
    assert client.get("/source-runs").status_code == 200


def test_raw_snapshots_endpoint():
    assert client.get("/raw-snapshots").status_code == 200


def test_data_endpoints_return_200():
    for path in [
        "/data/football/competitions",
        "/data/football/teams",
        "/data/football/matches",
        "/data/football/standings",
        "/data/lol/patches",
        "/data/lol/champions",
    ]:
        assert client.get(path).status_code == 200, path


def test_ui_pages_return_200():
    for path in ["/sources/ui", "/source-runs/ui", "/data/football/ui", "/data/lol/ui"]:
        response = client.get(path)
        assert response.status_code == 200, path
        assert "text/html" in response.headers["content-type"], path


def test_env_example_has_no_real_key():
    here = Path(__file__).resolve()
    candidate = None
    for parent in here.parents:
        maybe = parent / ".env.example"
        if maybe.exists():
            candidate = maybe
            break
    if candidate is None:
        pytest.skip(".env.example not present in this environment")
    for line in candidate.read_text(encoding="utf-8").splitlines():
        if line.startswith("FOOTBALL_DATA_API_KEY"):
            assert line.strip() == "FOOTBALL_DATA_API_KEY=", "API key must not be committed"
            return
    pytest.fail("FOOTBALL_DATA_API_KEY not found in .env.example")
