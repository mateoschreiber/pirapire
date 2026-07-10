import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_sync_disabled_mode_returns_manual():
    response = client.post('/aposta/sync', json={'force_aposta_refresh': False})
    assert response.status_code == 200
    data = response.json()
    assert 'status' in data
    assert 'run_id' in data


def test_aposta_status_has_all_fields():
    response = client.get('/aposta/status')
    assert response.status_code == 200
    data = response.json()
    assert 'current_odds' in data
    assert 'expired_odds' in data
    assert 'historical_odds' in data
    assert 'sync_mode' in data


def test_sync_response_has_counts():
    response = client.post('/aposta/sync', json={})
    data = response.json()
    assert 'run_id' in data
    assert 'status' in data
    assert 'message' in data


def test_aposta_options_respects_limit():
    response = client.get('/aposta/options?limit=2')
    assert response.status_code == 200
    data = response.json()
    assert len(data) <= 2


def test_unmapped_markets_returns_list():
    response = client.get('/aposta/unmapped-markets')
    assert response.status_code == 200
    assert isinstance(response.json(), list)
