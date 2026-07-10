import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_ok():
    response = client.get('/health')
    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ok'


def test_dashboard_state_returns_valid_json():
    response = client.get('/dashboard/state')
    assert response.status_code == 200
    data = response.json()
    assert 'health' in data
    assert data['health'] == 'ok'
    assert 'football' in data
    assert 'lol' in data
    assert 'aposta' in data
    assert 'recommendations' in data


def test_dashboard_state_football_keys():
    response = client.get('/dashboard/state')
    data = response.json()
    fb = data['football']
    for key in ('last_sync', 'stale', 'competitions', 'future_matches', 'finished_matches'):
        assert key in fb, f'Missing key {key} in football state'


def test_dashboard_state_lol_keys():
    response = client.get('/dashboard/state')
    data = response.json()
    lo = data['lol']
    for key in ('last_static_sync', 'history_last_import', 'games', 'teams', 'players', 'player_data_available'):
        assert key in lo, f'Missing key {key} in lol state'


def test_dashboard_state_aposta_keys():
    response = client.get('/dashboard/state')
    data = response.json()
    ap = data['aposta']
    for key in ('mode', 'last_snapshot', 'historical_odds', 'current_odds', 'expired_odds', 'unmapped_markets'):
        assert key in ap, f'Missing key {key} in aposta state'


def test_dashboard_state_recommendations_keys():
    response = client.get('/dashboard/state')
    data = response.json()
    rec = data['recommendations']
    for key in ('latest_run', 'singles', 'combos', 'blockers'):
        assert key in rec, f'Missing key {key} in recommendations state'


def test_dashboard_state_does_not_change_data():
    before = client.get('/dashboard/state').json()
    after = client.get('/dashboard/state').json()
    assert before == after


def test_dashboard_state_not_empty():
    response = client.get('/dashboard/state')
    assert response.status_code == 200
    data = response.json()
    assert data['football']['competitions'] >= 0
    assert data['aposta']['historical_odds'] >= 0
