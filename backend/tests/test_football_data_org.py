from sqlmodel import Session

from app.database import engine
from app.models_sources import SourceRun
from app.services import source_runs
from app.services.sync import football_sync
from app.sources.football.football_data_org import FootballDataOrgClient


def test_429_respects_retry_after_without_real_sleep():
    calls = {"n": 0}

    def requester(url, headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": False, "status": 429, "data": None, "error": "HTTP 429", "retry_after": "3"}
        return {"ok": True, "status": 200, "data": {"ok": 1}, "error": None, "retry_after": None}

    slept = []
    client = FootballDataOrgClient(
        "k", "http://test", request_delay=7, respect_retry_after=True,
        sleeper=lambda s: slept.append(s), requester=requester,
    )
    result = client.get_competition_matches("PL")
    assert result["ok"] is True
    assert calls["n"] == 2  # one retry
    assert 3.0 in slept  # honoured Retry-After (3s), not the default delay


def test_429_uses_default_delay_when_no_retry_after():
    calls = {"n": 0}

    def requester(url, headers=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": False, "status": 429, "data": None, "error": "HTTP 429", "retry_after": None}
        return {"ok": True, "status": 200, "data": {}, "error": None, "retry_after": None}

    slept = []
    client = FootballDataOrgClient(
        "k", "http://test", request_delay=5, respect_retry_after=True,
        sleeper=lambda s: slept.append(s), requester=requester,
    )
    client.get_competition_matches("PL")
    assert 5.0 in slept


def test_delay_between_consecutive_requests():
    def requester(url, headers=None):
        return {"ok": True, "status": 200, "data": {}, "error": None, "retry_after": None}

    slept = []
    client = FootballDataOrgClient(
        "k", "http://test", request_delay=5,
        sleeper=lambda s: slept.append(s), requester=requester,
    )
    client.get_competition_matches("A")  # first: no pacing wait
    client.get_competition_matches("B")  # second: pace 5s
    assert slept == [5.0]


class _FakeClient(FootballDataOrgClient):
    """Primary client stub: 'OK' competition succeeds, 'BAD' returns 429."""

    def __init__(self, *args, **kwargs):
        super().__init__("x", "http://test")

    def get_competition_matches(self, code, date_from=None, date_to=None):
        if code == "OK":
            return {
                "ok": True,
                "status": 200,
                "retry_after": None,
                "error": None,
                "data": {
                    "competition": {"id": 1, "name": "League", "code": "OK"},
                    "matches": [
                        {
                            "id": 500,
                            "utcDate": "2024-01-01T18:00:00Z",
                            "status": "FINISHED",
                            "matchday": 1,
                            "homeTeam": {"id": 1, "name": "A"},
                            "awayTeam": {"id": 2, "name": "B"},
                            "score": {"winner": "HOME_TEAM", "fullTime": {"home": 2, "away": 0}, "halfTime": {"home": 1, "away": 0}},
                        }
                    ],
                },
            }
        return {"ok": False, "status": 429, "data": None, "error": "HTTP 429", "retry_after": None}

    def get_competition_standings(self, code):
        return {"ok": True, "status": 200, "data": {"standings": [], "season": {}}, "error": None, "retry_after": None}


def test_football_sync_partial_on_mixed_results(monkeypatch):
    monkeypatch.setattr(football_sync.settings, "football_data_api_key", "x")
    monkeypatch.setattr(football_sync.settings, "football_data_competitions", "OK,BAD")
    monkeypatch.setattr(football_sync.settings, "football_data_max_competitions_per_run", 5)
    monkeypatch.setattr(football_sync, "FootballDataOrgClient", _FakeClient)

    with Session(engine) as session:
        run = source_runs.create_run(session, sport="football", source_slug=None)
        result = football_sync.sync(session, run)
        assert result["status"] == "partial"
        assert result["inserted"] >= 1  # OK competition inserted at least one match
        refreshed = session.get(SourceRun, run.id)
        assert refreshed.error_count >= 1  # BAD competition logged an error
