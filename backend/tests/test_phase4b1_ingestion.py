from urllib.parse import parse_qs, urlparse

from app.services import historical_ingestion as hi
from app.sources.football.api_football import ApiFootballClient


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


def test_api_football_uses_apisports_header_and_never_logs_key():
    seen = {}
    client = ApiFootballClient(
        "secret-key",
        "https://v3.football.api-sports.io",
        request_delay=0,
        requester=lambda url, headers=None: seen.update(headers or {}) or ok({"response": []}),
        sleeper=lambda _: None,
    )
    client.get_status()
    assert seen == {"x-apisports-key": "secret-key"}
    assert "secret-key" not in repr(client)


def test_api_football_team_fixtures_uses_season_param():
    urls = []
    client = ApiFootballClient(
        "k",
        "https://v3.football.api-sports.io",
        request_delay=0,
        requester=lambda url, headers=None: urls.append(url) or ok({"response": []}),
        sleeper=lambda _: None,
    )
    client.get_team_fixtures(26, 2024)
    parsed = urlparse(urls[0])
    assert parsed.path == "/fixtures"
    assert parse_qs(parsed.query) == {"team": ["26"], "season": ["2024"]}


def test_api_football_respects_request_cap():
    calls = {"n": 0}

    def req(url, headers=None):
        calls["n"] += 1
        return ok({"response": []})

    client = ApiFootballClient(
        "k", "https://v3.football.api-sports.io", request_delay=0,
        max_requests=3, requester=req, sleeper=lambda _: None,
    )
    for season in range(2016, 2022):  # distinct URLs to bypass cache
        client.get_team_fixtures(26, season)
    assert calls["n"] == 3
    assert client.budget_exhausted is True


def test_api_football_single_retry_on_429_then_stops():
    responses = [
        {"ok": False, "status": 429, "data": None, "error": "HTTP 429", "retry_after": "1", "content_type": "application/json"},
        {"ok": False, "status": 429, "data": None, "error": "HTTP 429", "retry_after": "1", "content_type": "application/json"},
    ]
    calls = {"n": 0}

    def req(url, headers=None):
        calls["n"] += 1
        return responses.pop(0)

    client = ApiFootballClient(
        "k", "https://v3.football.api-sports.io", request_delay=0,
        requester=req, sleeper=lambda _: None,
    )
    result = client.get_status()
    assert result["status"] == 429
    assert calls["n"] == 2  # original + exactly one retry


def test_regulation_penalties_exclude_shootouts():
    events = [
        {"team": {"id": 26}, "type": "Goal", "detail": "Penalty", "comments": None},
        {"team": {"id": 26}, "type": "Goal", "detail": "Penalty", "comments": "Penalty Shootout"},
        {"team": {"id": 26}, "type": "Goal", "detail": "Missed Penalty", "comments": None},
        {"team": {"id": 8}, "type": "Goal", "detail": "Normal Goal", "comments": None},
    ]
    out = hi._regulation_penalties_from_events(events)
    assert out[26]["penalties_scored"] == 1  # shootout excluded
    assert out[26]["penalties_missed"] == 1
    assert out.get(8, {}).get("penalties_scored", 0) == 0


def test_team_stats_mapping_preserves_null_and_maps_fields():
    resp = [
        {
            "team": {"id": 26},
            "statistics": [
                {"type": "Corner Kicks", "value": 11},
                {"type": "Total Shots", "value": 22},
                {"type": "Shots on Goal", "value": 9},
                {"type": "Fouls", "value": 9},
                {"type": "Yellow Cards", "value": 0},
                {"type": "Red Cards", "value": None},
            ],
        }
    ]
    mapped = hi._team_stats_from_response(resp)
    fields = mapped[26]
    assert fields["corners"] == 11
    assert fields["shots_total"] == 22
    assert fields["shots_on_target"] == 9
    assert fields["fouls"] == 9
    assert fields["yellow_cards"] == 0  # explicit zero preserved
    assert fields["red_cards"] is None  # null preserved, not zero


def test_to_int_never_turns_null_into_zero():
    assert hi._to_int(None) is None
    assert hi._to_int("") is None
    assert hi._to_int("None") is None
    assert hi._to_int(0) == 0
    assert hi._to_int("5") == 5
    assert hi._to_int("12%") == 12


def test_provider_errors_detects_plan_restrictions():
    assert hi._provider_errors(ok({"errors": {"plan": "no access"}})) == {"plan": "no access"}
    assert hi._provider_errors(ok({"errors": []})) is None
    assert hi._provider_errors(ok({"errors": {}})) is None
