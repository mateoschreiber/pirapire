from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_aposta_sync_manual_required_without_worker():
    resp = client.post("/aposta/sync")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] in ("manual_required", "unavailable")
    assert body["worker_configured"] is False
    assert "worker" in body["message"].lower()


def test_aposta_status():
    resp = client.get("/aposta/status")
    assert resp.status_code == 200
    assert resp.json()["worker_configured"] is False


def test_aposta_sync_runs_listed():
    client.post("/aposta/sync")
    runs = client.get("/aposta/sync-runs").json()
    assert len(runs) >= 1


def test_aposta_ui():
    assert client.get("/aposta/ui").status_code == 200


def test_recommendations_ui():
    assert client.get("/recommendations/ui").status_code == 200
