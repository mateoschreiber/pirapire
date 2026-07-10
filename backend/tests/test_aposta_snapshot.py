import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_aposta_status():
    response = client.get('/aposta/status')
    assert response.status_code == 200
    data = response.json()
    assert 'sync_mode' in data
    assert 'worker_configured' in data
    assert 'import_dir' in data


def test_aposta_current_odds():
    response = client.get('/aposta/options?include_stale=false&limit=50')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)


def test_aposta_historical_breakdown():
    response = client.get('/aposta/status')
    data = response.json()
    assert 'sync_mode' in data
    assert isinstance(data.get('current_odds', 0), int)
    assert isinstance(data.get('expired_odds', 0), int)
    assert isinstance(data.get('historical_odds', 0), int)


def test_dashboard_state_reflects_aposta():
    response = client.get('/dashboard/state')
    data = response.json()
    ap = data['aposta']
    assert 'current_odds' in ap
    assert 'expired_odds' in ap
    assert 'historical_odds' in ap


def test_aposta_unmapped():
    response = client.get('/aposta/unmapped-markets')
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
