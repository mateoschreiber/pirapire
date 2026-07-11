from urllib.parse import parse_qs, urlparse

import pytest

from app.services.integration_tester import _classify
from app.services.sync.thesportsdb_sync import _unambiguous_team
from app.sources.football.football_data_org import FootballDataOrgClient
from app.sources.football.thesportsdb import TheSportsDBClient
from app.sources.lol.riot_api import RiotAPIClient


def ok(data):
    return {
        "ok": True,
        "status": 200,
        "data": data,
        "error": None,
        "retry_after": None,
        "content_type": "application/json; charset=utf-8",
        "rate_limit": {},
    }


def test_football_team_matches_contract_uses_finished_and_limit():
    urls = []
    client = FootballDataOrgClient(
        "synthetic",
        "https://api.football-data.org/v4",
        requester=lambda url, headers=None: urls.append(url) or ok({"matches": []}),
    )
    client.get_team_matches(86)
    parsed = urlparse(urls[0])
    assert parsed.path == "/v4/teams/86/matches"
    assert parse_qs(parsed.query) == {"status": ["FINISHED"], "limit": ["10"]}


def test_thesportsdb_is_fixed_to_free_v1_and_encodes_parameters():
    urls = []
    client = TheSportsDBClient(
        "synthetic-public",
        requester=lambda url, headers=None: urls.append(url) or ok({"teams": []}),
        sleeper=lambda _: None,
    )
    client.search_teams("Paris & Saint-Germain")
    parsed = urlparse(urls[0])
    assert parsed.netloc == "www.thesportsdb.com"
    assert "/api/v1/json/" in parsed.path
    assert "/api/v2/" not in parsed.path
    assert parse_qs(parsed.query)["t"] == ["Paris & Saint-Germain"]
    assert "synthetic-public" not in repr(client)


def test_thesportsdb_rejects_wrong_sport_and_ambiguous_match():
    team = type("Team", (), {"name": "United", "short_name": None, "tla": None})()
    assert _unambiguous_team(
        [{"strSport": "Basketball", "strTeam": "United"}], team
    ) is None
    assert _unambiguous_team(
        [
            {"strSport": "Soccer", "strTeam": "United"},
            {"strSport": "Soccer", "strTeam": "United"},
        ],
        team,
    ) is None


def test_thesportsdb_honours_retry_after_once():
    calls = {"count": 0}
    slept = []

    def requester(url, headers=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return {"ok": False, "status": 429, "data": None, "error": "HTTP 429", "retry_after": "4"}
        return ok({"teams": []})

    client = TheSportsDBClient(
        "synthetic", requester=requester, sleeper=slept.append
    )
    assert client.search_teams("A")["ok"] is True
    assert calls["count"] == 2
    assert 4.0 in slept


def test_riot_routes_are_allowlisted_and_tokens_are_not_represented():
    urls = []
    client = RiotAPIClient(
        "synthetic-riot-token",
        platform="la2",
        region="americas",
        requester=lambda url, headers=None: urls.append(url) or ok([]),
        sleeper=lambda _: None,
    )
    client.match_ids_by_puuid("puuid / safe", count=5)
    parsed = urlparse(urls[0])
    assert parsed.netloc == "americas.api.riotgames.com"
    assert "%2F" in parsed.path
    assert "synthetic-riot-token" not in repr(client)
    with pytest.raises(ValueError, match="invalid_riot_route"):
        RiotAPIClient("x", platform="attacker.invalid", region="americas")


def test_riot_retries_429_but_not_unauthorized():
    responses = [
        {"ok": False, "status": 429, "data": None, "error": "HTTP 429", "retry_after": "2"},
        ok({"id": "status"}),
    ]
    slept = []
    client = RiotAPIClient(
        "synthetic", requester=lambda *args, **kwargs: responses.pop(0), sleeper=slept.append
    )
    assert client.get_platform_status()["ok"] is True
    assert 2.0 in slept

    calls = {"count": 0}
    unauthorized = {"ok": False, "status": 401, "data": None, "error": "HTTP 401", "retry_after": None}
    client = RiotAPIClient(
        "synthetic",
        requester=lambda *args, **kwargs: calls.update(count=calls["count"] + 1) or unauthorized,
        sleeper=lambda _: None,
    )
    assert client.get_platform_status()["status"] == 401
    assert calls["count"] == 1


def test_provider_error_classification_is_specific():
    assert _classify({"ok": False, "status": 401, "error": "HTTP 401"})["error_code"] == "invalid_key"
    assert _classify({"ok": False, "status": 403, "error": "HTTP 403"})["error_code"] == "forbidden"
    assert _classify({"ok": False, "status": 429, "error": "HTTP 429"})["error_code"] == "quota_exceeded"
