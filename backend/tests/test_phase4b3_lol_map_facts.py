from datetime import UTC, datetime

from sqlmodel import Session, select

from app.database import engine
from app.models_football import FootballFixtureStat
from app.models_lol import LolGameHistory, LolPlayerGameStat, LolSeries, LolTeamGameStat
from app.services import historical_ingestion as hi


def _cleanup_lol(session, marker="t4b3"):
    for model in (LolPlayerGameStat, LolTeamGameStat, LolGameHistory):
        for r in session.exec(select(model).where(model.source_game_id.like(f"{marker}%"))).all():
            session.delete(r)
    for r in session.exec(select(LolSeries).where(LolSeries.match_id.like(f"{marker}%"))).all():
        session.delete(r)
    session.commit()


def test_stale_football_is_not_eligible():
    with Session(engine) as s:
        row = FootballFixtureStat(
            provider="api_football_test4b3", fixture_id="t4b3_f1", team_side="home",
            team_name="StaleFC", kickoff_utc=datetime(2024, 1, 1, tzinfo=UTC),
            freshness_class="historical_fallback_stale", eligible_for_last_n=False,
            candidate_last_n=True, source_key="t4b3|f1|home",
        )
        s.add(row)
        s.commit()
        # Invariant: any stale row must have eligible_for_last_n=False.
        stale = s.exec(select(FootballFixtureStat).where(
            FootballFixtureStat.freshness_class == "historical_fallback_stale",
            FootballFixtureStat.eligible_for_last_n == True,  # noqa: E712
        )).all()
        assert stale == []
        s.delete(row)
        s.commit()


def test_gameid_without_matchid_not_grouped():
    rows = [
        {"MatchId": "MX", "GameId": "MX_1", "Team1": "A", "Team2": "B"},
        {"MatchId": "", "GameId": "orphan_1", "Team1": "A", "Team2": "C"},
    ]
    grouped = hi._group_series(rows)
    assert "MX" in grouped
    assert all(mid for mid in grouped)  # no empty MatchId keys
    assert "" not in grouped


def test_map_game_persists_and_derives_deaths_from_opponent_kills():
    with Session(engine) as s:
        _cleanup_lol(s)
        m = {
            "MatchId": "t4b3_M1", "GameId": "t4b3_M1_1", "N GameInMatch": 1,
            "DateTime UTC": "2026-05-01 10:00:00", "OverviewPage": "TestLeague",
            "Team1": "Alpha", "Team2": "Beta", "Winner": 1, "WinTeam": "Alpha",
            "Gamelength Number": 30.5, "Team1Kills": 15, "Team2Kills": 4,
            "Team1Towers": 9, "Team2Towers": 2, "Team1Inhibitors": 2, "Team2Inhibitors": 0,
        }
        hi._upsert_map_game(s, m, datetime.now(UTC))
        stats = s.exec(select(LolTeamGameStat).where(LolTeamGameStat.source_game_id == "t4b3_M1_1")).all()
        assert len(stats) == 2
        by_team = {st.team_name: st for st in stats}
        assert by_team["Alpha"].team_kills == 15
        assert by_team["Alpha"].team_deaths == 4   # opponent kills
        assert by_team["Beta"].team_kills == 4
        assert by_team["Beta"].team_deaths == 15
        assert by_team["Alpha"].result == 1 and by_team["Beta"].result == 0
        assert by_team["Alpha"].game_length_seconds == 1830
        _cleanup_lol(s)


def test_no_duplicate_maps_or_players_on_second_upsert():
    with Session(engine) as s:
        _cleanup_lol(s)
        m = {"MatchId": "t4b3_M2", "GameId": "t4b3_M2_1", "N GameInMatch": 1,
             "DateTime UTC": "2026-05-02 10:00:00", "Team1": "A", "Team2": "B",
             "Winner": 1, "WinTeam": "A", "Team1Kills": 5, "Team2Kills": 3}
        players = [
            {"GameId": "t4b3_M2_1", "Name": "p1", "Team": "A", "Role": "Top", "Kills": 2, "Deaths": 1, "Assists": 3},
            {"GameId": "t4b3_M2_1", "Name": "p1", "Team": "A", "Role": "Top", "Kills": 2, "Deaths": 1, "Assists": 3},
        ]
        now = datetime.now(UTC)
        hi._upsert_map_game(s, m, now)
        hi._upsert_map_game(s, m, now)  # second time: no dup
        n1 = hi._upsert_map_players(s, "t4b3_M2_1", players, now)
        n2 = hi._upsert_map_players(s, "t4b3_M2_1", players, now)
        games = s.exec(select(LolGameHistory).where(LolGameHistory.source_game_id == "t4b3_M2_1")).all()
        teams = s.exec(select(LolTeamGameStat).where(LolTeamGameStat.source_game_id == "t4b3_M2_1")).all()
        pls = s.exec(select(LolPlayerGameStat).where(LolPlayerGameStat.source_game_id == "t4b3_M2_1")).all()
        assert len(games) == 1
        assert len(teams) == 2
        assert len(pls) == 1  # duplicate player (same gameid+name+team) collapsed
        assert n1 == 1 and n2 == 0
        _cleanup_lol(s)


def test_series_incomplete_when_maps_missing():
    with Session(engine) as s:
        _cleanup_lol(s)
        import json
        srow = LolSeries(
            source_name="leaguepedia", match_id="t4b3_S1", source_key="leaguepedia|t4b3_S1",
            team1="A", team2="B", date="2026-05-03 10:00:00",
            game_ids_json=json.dumps(["t4b3_S1_1", "t4b3_S1_2"]),
        )
        s.add(srow)
        s.commit()
        # Only one of the two published maps stored -> partial.
        m = {"MatchId": "t4b3_S1", "GameId": "t4b3_S1_1", "N GameInMatch": 1,
             "DateTime UTC": "2026-05-03 10:00:00", "Team1": "A", "Team2": "B",
             "Winner": 1, "WinTeam": "A", "Team1Kills": 1, "Team2Kills": 0}
        hi._upsert_map_game(s, m, datetime.now(UTC))
        status = hi._update_series_status(s, srow)
        assert status == "partial"
        assert srow.eligible_for_last_n is False
        _cleanup_lol(s)


def test_series_complete_when_all_maps_present_with_results():
    with Session(engine) as s:
        _cleanup_lol(s)
        import json
        srow = LolSeries(
            source_name="leaguepedia", match_id="t4b3_S2", source_key="leaguepedia|t4b3_S2",
            team1="A", team2="B", date="2026-05-04 10:00:00",
            game_ids_json=json.dumps(["t4b3_S2_1", "t4b3_S2_2"]),
        )
        s.add(srow)
        s.commit()
        for i in (1, 2):
            hi._upsert_map_game(s, {
                "MatchId": "t4b3_S2", "GameId": f"t4b3_S2_{i}", "N GameInMatch": i,
                "DateTime UTC": "2026-05-04 10:00:00", "Team1": "A", "Team2": "B",
                "Winner": 1, "WinTeam": "A", "Team1Kills": 1, "Team2Kills": 0,
            }, datetime.now(UTC))
        status = hi._update_series_status(s, srow)
        assert status == "complete"
        _cleanup_lol(s)
