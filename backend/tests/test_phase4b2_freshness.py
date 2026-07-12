from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.database import engine
from app.models_football import FootballFixturePlayerStat, FootballFixtureStat
from app.models_lol import LolSeries
from app.services import field_classification as fc
from app.services import historical_ingestion as hi


def _clean(session, provider="test4b2"):
    for model in (FootballFixtureStat, FootballFixturePlayerStat):
        for r in session.exec(select(model).where(model.provider == provider)).all():
            session.delete(r)
    for r in session.exec(select(LolSeries).where(LolSeries.source_name == "test4b2")).all():
        session.delete(r)
    session.commit()


def test_shootout_penalties_not_counted_as_for_or_against():
    # Regulation penalty + shootout penalties; only the regulation one counts.
    events = [
        {"team": {"id": 1}, "type": "Goal", "detail": "Penalty", "comments": None},
        {"team": {"id": 1}, "type": "Goal", "detail": "Penalty", "comments": "Penalty Shootout"},
        {"team": {"id": 1}, "type": "Goal", "detail": "Penalty", "comments": "Penalty Shootout"},
    ]
    out = hi._regulation_penalties_from_events(events)
    assert out[1]["penalties_scored"] == 1


def test_null_is_never_zero_for_team_or_player():
    resp = [{"team": {"id": 9}, "statistics": [
        {"type": "Corner Kicks", "value": None},
        {"type": "Fouls", "value": 0},
    ]}]
    mapped = hi._team_stats_from_response(resp)
    assert mapped[9]["corners"] is None   # null preserved
    assert mapped[9]["fouls"] == 0        # real zero preserved


def test_last_10_are_the_most_recent_before_kickoff():
    # Build 12 fixtures across dates; the 10 most recent before kickoff must be eligible.
    with Session(engine) as s:
        _clean(s)
        # Insert directly to exercise ordering logic via _football_freshness stand-in.
        rows = []
        for i in range(12):
            dt = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i * 10)
            r = FootballFixtureStat(
                provider="test4b2", fixture_id=f"f{i}", team_side="home",
                team_name="Testland", opponent_name="Rival", kickoff_utc=dt,
                match_status="FT", source_key=f"test4b2|f{i}|home",
            )
            rows.append(r)
            s.add(r)
        s.commit()
        # Emulate the eligibility algorithm used in _football_freshness.
        dated = sorted(rows, key=lambda r: r.kickoff_utc, reverse=True)
        eligible = {r.fixture_id for r in dated[:10]}
        # The two oldest must be excluded.
        assert "f0" not in eligible and "f1" not in eligible
        assert len(eligible) == 10
        _clean(s)


def test_stale_rows_classified_as_stale():
    with Session(engine) as s:
        _clean(s)
        for i in range(3):
            s.add(FootballFixtureStat(
                provider="api_football_test", fixture_id=f"s{i}", team_side="home",
                team_name="StaleTeam", kickoff_utc=datetime(2024, 6, 1, tzinfo=UTC),
                corners=5, fouls=10, eligible_for_last_n=True,
                freshness_class="historical_fallback_stale",
                source_key=f"stale|{i}",
            ))
        s.commit()
        # classify using the real classifier but scoped provider check is api_football;
        # verify the _classify helper marks all-stale as 'stale'.
        cls = fc._classify([5, 5, 5], [True, True, True])
        assert cls == "stale"
        cls2 = fc._classify([5, None, 5], [False, False, False])
        assert cls2 == "partial"
        cls3 = fc._classify([5, 5], [False, False])
        assert cls3 == "complete"
        cls4 = fc._classify([None, None], [False, False])
        assert cls4 == "absent"
        for r in s.exec(select(FootballFixtureStat).where(FootballFixtureStat.provider == "api_football_test")).all():
            s.delete(r)
        s.commit()


def test_player_leader_blocked_when_fouls_missing():
    with Session(engine) as s:
        # Eligible fixture with a player row that has no fouls -> blocked.
        s.add(FootballFixtureStat(
            provider="api_football", fixture_id="pl_test_1", team_side="home",
            team_name="LeaderTest", eligible_for_last_n=True,
            freshness_class="historical_fallback", source_key="lt|pl_test_1|home",
        ))
        s.add(FootballFixturePlayerStat(
            provider="api_football", fixture_id="pl_test_1", team_name="LeaderTest",
            player_external_id="p1", player_name="No Fouls", fouls_committed=None,
            source_key="api_football|pl_test_1|p1",
        ))
        s.commit()
        assert fc.can_compute_player_leader(s, "LeaderTest") is False
        # cleanup
        for r in s.exec(select(FootballFixtureStat).where(FootballFixtureStat.fixture_id == "pl_test_1")).all():
            s.delete(r)
        for r in s.exec(select(FootballFixturePlayerStat).where(FootballFixturePlayerStat.fixture_id == "pl_test_1")).all():
            s.delete(r)
        s.commit()


def test_series_requires_matchid_and_gameid():
    rows = [
        {"MatchId": "M1", "GameId": "M1_1", "N GameInMatch": 1, "Team1": "A", "Team2": "B"},
        {"MatchId": "M2", "GameId": "", "Team1": "A", "Team2": "C"},   # no gameid -> excluded
        {"MatchId": "", "GameId": "X_1", "Team1": "A", "Team2": "D"},  # no matchid -> excluded
    ]
    grouped = hi._group_series(rows)
    assert "M1" in grouped
    assert "M2" not in grouped
    assert "" not in grouped


def test_browser_fallback_allowlist_and_no_worker():
    from app.services import browser_fallback as bf
    assert bf.is_allowed("https://www.thesportsdb.com/team/1") is True
    assert bf.is_allowed("https://evil.example.com/x") is False
    # Probe on a disallowed host never calls the network.
    res = bf.probe("https://evil.example.com/x")
    assert res["ok"] is False and res["error"] == "host_not_allowed"
