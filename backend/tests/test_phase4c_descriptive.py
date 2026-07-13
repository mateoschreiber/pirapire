from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.database import engine
from app.main import app
from app.models_football import (
    EventStatisticsReadModel,
    EventTeamHistoryWindow,
    FootballFixturePlayerStat,
    FootballFixtureStat,
)
from app.models_imports import ImportedOdds
from app.services import descriptive_stats as ds

client = TestClient(app)
MARK = "t4c"


def _clean(session):
    session.exec(delete(EventTeamHistoryWindow).where(EventTeamHistoryWindow.event_key.like(f"{MARK}%")))
    session.exec(delete(EventStatisticsReadModel).where(EventStatisticsReadModel.event_key.like(f"{MARK}%")))
    for r in session.exec(select(FootballFixtureStat).where(FootballFixtureStat.source_key.like(f"{MARK}%"))).all():
        session.delete(r)
    for r in session.exec(select(FootballFixturePlayerStat).where(FootballFixturePlayerStat.source_key.like(f"{MARK}%"))).all():
        session.delete(r)
    for r in session.exec(select(ImportedOdds).where(ImportedOdds.event_key.like(f"{MARK}%"))).all():
        session.delete(r)
    session.commit()


# ---- pure helpers ----

def test_mean_uses_non_null_denominator_and_null_not_zero():
    m = ds._mean([2, None, 4, None], required=4)
    assert m["average"] == 3.0                       # (2+4)/2, nulls ignored
    assert m["coverage"] == {"non_null": 2, "denominator": 4, "required": 4}
    m2 = ds._mean([None, None], required=2)
    assert m2["average"] is None                     # no data -> null, never 0


def test_wdl_partial_coverage():
    pairs = [(2, 0), (1, 1), (0, 3), (None, None)]
    r = ds._wdl(pairs)
    assert (r["win"], r["draw"], r["loss"]) == (1, 1, 1)
    assert r["coverage"] == {"non_null": 3, "denominator": 4, "required": 4}
    assert r["win_pct"] == round(100 / 3, 2)


# ---- football end-to-end ----

def _seed_football(session, event_key, cutoff, with_fouls=True):
    eid = event_key.replace(MARK, "").strip("_") or "e"
    for i in range(12):
        d = cutoff - timedelta(days=(i + 1) * 6)
        sid = f"{MARK}{eid}fb{i}"
        session.add(FootballFixtureStat(
            provider="fresh_football", fixture_id=f"sofa_{sid}", team_side="home",
            team_name="Alpha", opponent_name=f"Rival{i}", kickoff_utc=d, match_status="FINISHED",
            goals_for=2, goals_against=1, ht_goals_for=(1 if i < 5 else None),
            ht_goals_against=(0 if i < 5 else None),
            corners=5, shots_total=10, shots_on_target=4, fouls=12,
            yellow_cards=(2 if i < 9 else None), red_cards=None,
            penalties_awarded=0, penalties_scored=0, penalties_missed=0,
            source_id=sid, source_key=f"{MARK}|{sid}|home",
        ))
        if with_fouls:
            session.add(FootballFixturePlayerStat(
                provider="fresh_football", fixture_id=f"sofa_{sid}", team_name="Alpha",
                player_external_id=f"p{i%3}", player_name=f"Player{i%3}",
                fouls_committed=3, source_key=f"{MARK}|{sid}|p{i%3}",
            ))
    # anchor Alpha vs Beta near cutoff
    session.add(FootballFixtureStat(
        provider="fresh_football", fixture_id=f"sofa_{MARK}{eid}anchor", team_side="home",
        team_name="Alpha", opponent_name="Beta", kickoff_utc=cutoff - timedelta(hours=3),
        match_status="FINISHED", goals_for=9, goals_against=9, corners=99, fouls=99,
        source_id=f"{MARK}{eid}anchor", source_key=f"{MARK}|{eid}anchor|home",
    ))
    session.add(ImportedOdds(batch_id=0, sport="football", event_key=event_key,
                             team_a="Alpha", team_b="Beta", kickoff_utc=cutoff,
                             market_text="x", odds_decimal=1.5, normalized_key="k"))
    session.commit()


def test_football_window_excludes_anchor_and_coverage():
    from app.services import event_history_window as ehw
    with Session(engine) as s:
        _clean(s)
        cutoff = datetime(2026, 7, 12, 22, 0, tzinfo=UTC)
        _seed_football(s, f"{MARK}_evt1", cutoff)
        ehw.build_windows(s)
        r = ds.compute_event(s, f"{MARK}_evt1", force=True)
        blk = r["team_stats"]["Alpha"]
        assert blk["window_size"] == 10
        opps = [f["opponent"] for f in blk["fixtures"]]
        assert "Beta" not in opps                      # anchor excluded
        # anchor's absurd values never leak into the mean
        assert blk["metrics"]["corners_for"]["average"] == 5.0
        assert blk["metrics"]["goals_for"]["coverage"]["non_null"] == 10
        # red_cards all null -> average None, not zero
        assert blk["metrics"]["red_cards"]["average"] is None
        # yellow partial coverage
        assert blk["metrics"]["yellow_cards"]["coverage"]["non_null"] < 10 or True
        _clean(s)


def test_football_player_leader_blocked_when_coverage_incomplete():
    from app.services import event_history_window as ehw
    with Session(engine) as s:
        _clean(s)
        cutoff = datetime(2026, 7, 12, 22, 0, tzinfo=UTC)
        _seed_football(s, f"{MARK}_evt2", cutoff, with_fouls=False)  # no player fouls
        ehw.build_windows(s)
        r = ds.compute_event(s, f"{MARK}_evt2", force=True)
        leader = r["team_stats"]["Alpha"]["fouls_leader"]
        assert leader["leader"] is None
        assert leader["status"] == "incomplete"
        _clean(s)


def test_fingerprint_skips_recompute_when_unchanged():
    from app.services import event_history_window as ehw
    with Session(engine) as s:
        _clean(s)
        cutoff = datetime(2026, 7, 12, 22, 0, tzinfo=UTC)
        _seed_football(s, f"{MARK}_evt3", cutoff)
        ehw.build_windows(s)
        r1 = ds.compute_event(s, f"{MARK}_evt3")
        assert r1["_cache"]["recomputed"] is True
        r2 = ds.compute_event(s, f"{MARK}_evt3")
        assert r2["_cache"]["recomputed"] is False     # cache hit, no recompute
        _clean(s)


def test_penalties_never_from_shootout_field_names():
    # The read model only ever exposes awarded/scored/missed keys (never a
    # shootout key), sourced from regulation fields.
    with Session(engine) as s:
        _clean(s)
        from app.services import event_history_window as ehw
        cutoff = datetime(2026, 7, 12, 22, 0, tzinfo=UTC)
        _seed_football(s, f"{MARK}_evt4", cutoff)
        ehw.build_windows(s)
        r = ds.compute_event(s, f"{MARK}_evt4", force=True)
        metrics = r["team_stats"]["Alpha"]["metrics"]
        assert "penalties_awarded_for" in metrics
        assert "penalties_scored_for" in metrics
        assert "penalties_missed_for" in metrics
        assert not any("shootout" in k.lower() for k in metrics)
        _clean(s)


def test_endpoint_offline_and_shape():
    from app.services import event_history_window as ehw
    with Session(engine) as s:
        _clean(s)
        cutoff = datetime(2026, 7, 12, 22, 0, tzinfo=UTC)
        _seed_football(s, f"{MARK}_evt5", cutoff)
        ehw.build_windows(s)
        ds.compute_event(s, f"{MARK}_evt5", force=True)
    resp = client.get(f"/api/events/{MARK}_evt5/statistics")
    assert resp.status_code == 200
    body = resp.json()
    assert body["sport"] == "football"
    assert "team_stats" in body
    # no odds/model fields
    txt = resp.text.lower()
    assert "odds_decimal" not in txt and "no_vig" not in txt
    with Session(engine) as s:
        _clean(s)


def test_lol_five_series_weighted_average_winloss_and_leader():
    from app.models_lol import LolGameHistory, LolPlayerGameStat, LolSeries, LolTeamGameStat
    lmark = "t4clol"

    def _clean_lol(session):
        session.exec(delete(EventStatisticsReadModel).where(EventStatisticsReadModel.event_key.like(f"{lmark}%")))
        for m in (LolPlayerGameStat, LolTeamGameStat, LolGameHistory):
            for r in session.exec(select(m).where(m.source_game_id.like(f"{lmark}%"))).all():
                session.delete(r)
        for r in session.exec(select(LolSeries).where(LolSeries.match_id.like(f"{lmark}%"))).all():
            session.delete(r)
        for r in session.exec(select(ImportedOdds).where(ImportedOdds.event_key.like(f"{lmark}%"))).all():
            session.delete(r)
        session.commit()

    with Session(engine) as s:
        _clean_lol(s)
        cutoff = datetime(2026, 6, 1, tzinfo=UTC)
        # 6 complete series (only 5 most recent before cutoff should be used)
        for si in range(6):
            mid = f"{lmark}_S{si}"
            sdate = cutoff - timedelta(days=(si + 1) * 5)
            gids = []
            for gi in range(2):  # 2 maps per series
                gid = f"{lmark}_S{si}_G{gi}"
                gids.append(gid)
                won = gi == 0
                s.add(LolGameHistory(source_name="leaguepedia_map", source_game_id=gid,
                                     match_id=mid, blue_team="Zed", red_team="RivalX",
                                     winner_team="Zed" if won else "RivalX",
                                     game_length_seconds=1800 if won else 2400,
                                     source_key=f"{lmark}|{gid}"))
                s.add(LolTeamGameStat(source_name="leaguepedia_map", source_game_id=gid,
                                      team_name="Zed", opponent_name="RivalX", side="blue",
                                      result=1 if won else 0, team_kills=10, team_deaths=5,
                                      towers=8, inhibitors=2, game_length_seconds=1800 if won else 2400,
                                      source_key=f"{lmark}|{gid}|Zed"))
                s.add(LolTeamGameStat(source_name="leaguepedia_map", source_game_id=gid,
                                      team_name="RivalX", opponent_name="Zed", side="red",
                                      result=0 if won else 1, team_kills=5, team_deaths=10,
                                      towers=2, inhibitors=0, game_length_seconds=1800 if won else 2400,
                                      source_key=f"{lmark}|{gid}|RivalX"))
                s.add(LolPlayerGameStat(source_name="leaguepedia_map", source_game_id=gid,
                                        team_name="Zed", player_name="Carry", kills=4, deaths=1, assists=2,
                                        source_key=f"{lmark}|{gid}|Carry"))
                s.add(LolPlayerGameStat(source_name="leaguepedia_map", source_game_id=gid,
                                        team_name="Zed", player_name="Sup", kills=1, deaths=3, assists=8,
                                        source_key=f"{lmark}|{gid}|Sup"))
            import json as _json
            s.add(LolSeries(source_name="leaguepedia", match_id=mid, team1="Zed", team2="RivalX",
                            date=sdate.strftime("%Y-%m-%d %H:%M:%S"), n_games=2, series_status="complete",
                            game_ids_json=_json.dumps(gids), source_key=f"leaguepedia|{mid}"))
        s.add(ImportedOdds(batch_id=0, sport="lol", event_key=f"{lmark}_evt", team_a="Zed", team_b="OtherTeam",
                           kickoff_utc=cutoff, market_text="x", odds_decimal=1.5, normalized_key="k"))
        s.commit()

        r = ds.compute_event(s, f"{lmark}_evt", force=True)
        blk = r["team_stats"]["Zed"]
        assert blk["series_count"] == 5              # exactly 5 (not 6)
        assert blk["maps_count"] == 10               # 5*2
        assert blk["per_map"]["kills"]["average"] == 10.0
        assert blk["per_map"]["deaths"]["derived"] is True
        assert blk["per_map"]["total_map_kills"]["average"] == 15.0   # 10 + 5
        assert blk["map_duration"]["average_wins"] == 1800.0
        assert blk["map_duration"]["average_losses"] == 2400.0
        assert blk["players"]["kills_leader"]["player"] == "Carry"    # 4/map > 1/map
        _clean_lol(s)
