import json
from pathlib import Path

from sqlmodel import Session

from app.database import engine
from app.models_sources import SourceRun
from app.services import raw_snapshots, source_runs
from app.sources.football.football_data_org import FootballDataOrgClient
from app.sources.football.openligadb import OpenLigaDBClient
from app.sources.lol.datadragon import RiotDataDragonClient

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load(name):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def test_football_client_builds_auth_header_without_leaking_token():
    client = FootballDataOrgClient("secret-token-123", "https://api.football-data.org/v4")
    headers = client.headers()
    assert headers == {"X-Auth-Token": "secret-token-123"}
    # The token must not be exposed via the default object repr.
    assert "secret-token-123" not in repr(client)


def test_football_client_empty_key_has_no_auth_header():
    client = FootballDataOrgClient("", "https://api.football-data.org/v4")
    assert client.headers() == {}


def test_football_normalize_matches_and_scores():
    data = load("football_data_matches.json")
    finished = FootballDataOrgClient.normalize_match(data["matches"][0])
    assert finished["source_external_id"] == "12345"
    assert finished["home_score"] == 2
    assert finished["away_score"] == 1
    assert finished["ht_home_score"] == 1
    assert finished["ht_away_score"] == 0
    assert finished["winner"] == "HOME_TEAM"
    assert finished["home_team"]["id"] == 57

    scheduled = FootballDataOrgClient.normalize_match(data["matches"][1])
    assert scheduled["status"] == "SCHEDULED"
    assert scheduled["home_score"] is None
    assert scheduled["ht_home_score"] is None


def test_football_normalize_competition():
    data = load("football_data_matches.json")
    comp = FootballDataOrgClient.normalize_competition(data["competition"])
    assert comp["source_external_id"] == "2021"
    assert comp["code"] == "PL"
    assert comp["country"] == "England"


def test_football_normalize_standings_uses_total_only():
    data = load("football_data_standings.json")
    rows = FootballDataOrgClient.normalize_standings(data)
    assert len(rows) == 1
    row = rows[0]
    assert row["position"] == 1
    assert row["points"] == 3
    assert row["goal_difference"] == 1
    assert row["season"] == "2024"
    assert row["team"]["id"] == 57


def test_openligadb_normalize_match_marks_scores():
    raw = {
        "matchID": 999,
        "matchDateTimeUTC": "2024-08-16T17:30:00Z",
        "matchIsFinished": True,
        "team1": {"teamId": 7, "teamName": "Bayern", "shortName": "FCB"},
        "team2": {"teamId": 8, "teamName": "Dortmund", "shortName": "BVB"},
        "matchResults": [
            {"resultTypeID": 1, "pointsTeam1": 1, "pointsTeam2": 0},
            {"resultTypeID": 2, "pointsTeam1": 3, "pointsTeam2": 1},
        ],
    }
    nm = OpenLigaDBClient.normalize_match(raw)
    assert nm["source_external_id"] == "999"
    assert nm["home_score"] == 3
    assert nm["away_score"] == 1
    assert nm["ht_home_score"] == 1
    assert nm["status"] == "FINISHED"
    assert nm["home_team"]["id"] == 7


def test_datadragon_versions_and_champions():
    versions = load("datadragon_versions.json")
    assert RiotDataDragonClient.latest_version(versions) == "14.1.1"
    assert RiotDataDragonClient.latest_version([]) is None

    champ_json = load("datadragon_champion.json")
    champs = RiotDataDragonClient.normalize_champions(champ_json, "14.1.1")
    ids = [c["champion_id"] for c in champs]
    assert "Aatrox" in ids and "Ahri" in ids
    aatrox = next(c for c in champs if c["champion_id"] == "Aatrox")
    assert aatrox["champion_key"] == "266"
    assert aatrox["version"] == "14.1.1"


def test_raw_snapshot_hash_is_stable_and_order_independent():
    h1 = raw_snapshots.payload_hash({"b": 2, "a": 1})
    h2 = raw_snapshots.payload_hash({"a": 1, "b": 2})
    assert h1 == h2
    assert raw_snapshots.payload_hash({"a": 1}) != h1


def test_raw_snapshot_dedup():
    payload = {"sample": [1, 2, 3]}
    with Session(engine) as session:
        run = source_runs.create_run(session, sport="football", source_slug="football_data_org")
        snap1, new1 = raw_snapshots.save_snapshot(
            session, run.id, "football_data_org", "football", "matches", payload, external_id="dedup"
        )
        snap2, new2 = raw_snapshots.save_snapshot(
            session, run.id, "football_data_org", "football", "matches", payload, external_id="dedup"
        )
        assert new1 is True
        assert new2 is False
        assert snap1.id == snap2.id


def test_source_run_running_to_success():
    with Session(engine) as session:
        run = source_runs.create_run(session, sport="lol", source_slug="riot_datadragon")
        assert run.status == "running"
        source_runs.finalize(session, run, "success", inserted=5, updated=1, skipped=0)
        refreshed = session.get(SourceRun, run.id)
        assert refreshed.status == "success"
        assert refreshed.total_records == 6
        assert refreshed.finished_at is not None
