from datetime import UTC, datetime, timedelta

from sqlmodel import Session, delete, select

from app.database import engine
from app.models_football import EventTeamHistoryWindow, FootballFixtureStat
from app.models_imports import ImportedOdds
from app.services import event_history_window as ehw


MARK = "t4b41"


def _u(dt):
    return dt.replace(tzinfo=UTC) if (dt is not None and dt.tzinfo is None) else dt


def _clean(session):
    session.exec(delete(EventTeamHistoryWindow).where(EventTeamHistoryWindow.event_key.like(f"{MARK}%")))
    for r in session.exec(select(FootballFixtureStat).where(FootballFixtureStat.fixture_id.like(f"{MARK}%"))).all():
        session.delete(r)
    for r in session.exec(select(ImportedOdds).where(ImportedOdds.event_key.like(f"{MARK}%"))).all():
        session.delete(r)
    session.commit()


def _mk_fixture(session, team, opp, kickoff, sid):
    session.add(FootballFixtureStat(
        provider="fresh_football", fixture_id=f"{MARK}_{sid}", team_side="home",
        team_name=team, opponent_name=opp, kickoff_utc=kickoff, match_status="FINISHED",
        source_id=sid, source_key=f"{MARK}|{sid}|home",
    ))


def test_english_name_map():
    assert ehw._english_name("Suiza") == "Switzerland"
    assert ehw._english_name("Argentina") == "Argentina"


def test_anchor_excluded_and_ranks_before_cutoff():
    with Session(engine) as s:
        _clean(s)
        cutoff = datetime(2026, 7, 12, 22, 0, tzinfo=UTC)
        # 12 historical fixtures for TeamA + the anchor vs TeamB near cutoff.
        for i in range(12):
            d = cutoff - timedelta(days=(i + 1) * 6)
            _mk_fixture(s, "TeamA", f"Rival{i}", d, f"{MARK}h{i}")
        # anchor: TeamA vs TeamB at the event time (01:00 same match-day style).
        _mk_fixture(s, "TeamA", "TeamB", datetime(2026, 7, 12, 1, 0, tzinfo=UTC), f"{MARK}anchor")
        s.add(ImportedOdds(
            batch_id=0, sport="football", event_key=f"{MARK}_evt1",
            team_a="TeamA", team_b="TeamB", kickoff_utc=cutoff,
            market_text="x", odds_decimal=1.5, normalized_key="k",
        ))
        s.commit()

        ehw.build_windows(s)
        rows = ehw.window_for(s, f"{MARK}_evt1", "TeamA")
        assert len(rows) == 10
        # ranks 1..10 contiguous, all before cutoff, none is the anchor.
        assert [r.rank for r in rows] == list(range(1, 11))
        for r in rows:
            assert _u(r.kickoff_utc) < cutoff
            assert not (r.opponent == "TeamB")     # anchor excluded
        _clean(s)


def test_anchor_available_for_a_later_event():
    with Session(engine) as s:
        _clean(s)
        # The anchor match (TeamA vs TeamB on 07-12) must be usable by a LATER
        # event's window (e.g. TeamA's next match on 07-20).
        _mk_fixture(s, "TeamA", "TeamB", datetime(2026, 7, 12, 1, 0, tzinfo=UTC), f"{MARK}hh")
        for i in range(9):
            d = datetime(2026, 7, 12, 1, 0, tzinfo=UTC) - timedelta(days=(i + 1) * 6)
            _mk_fixture(s, "TeamA", f"Old{i}", d, f"{MARK}o{i}")
        later = datetime(2026, 7, 20, 20, 0, tzinfo=UTC)
        s.add(ImportedOdds(
            batch_id=0, sport="football", event_key=f"{MARK}_evtLater",
            team_a="TeamA", team_b="TeamC", kickoff_utc=later,
            market_text="x", odds_decimal=1.5, normalized_key="k",
        ))
        s.commit()
        ehw.build_windows(s)
        rows = ehw.window_for(s, f"{MARK}_evtLater", "TeamA")
        opps = [r.opponent for r in rows]
        # The 07-12 head-to-head vs TeamB is now a valid historical match here.
        assert "TeamB" in opps
        assert all(_u(r.kickoff_utc) < later for r in rows)
        _clean(s)


def test_build_is_idempotent():
    with Session(engine) as s:
        _clean(s)
        cutoff = datetime(2026, 6, 1, tzinfo=UTC)
        for i in range(10):
            _mk_fixture(s, "TeamX", f"R{i}", cutoff - timedelta(days=(i + 1) * 5), f"{MARK}x{i}")
        s.add(ImportedOdds(batch_id=0, sport="football", event_key=f"{MARK}_evtX",
                           team_a="TeamX", team_b="TeamY", kickoff_utc=cutoff,
                           market_text="x", odds_decimal=1.5, normalized_key="k"))
        s.commit()
        ehw.build_windows(s)
        n1 = len(ehw.window_for(s, f"{MARK}_evtX", "TeamX"))
        ehw.build_windows(s)
        n2 = len(ehw.window_for(s, f"{MARK}_evtX", "TeamX"))
        assert n1 == n2 == 10
        _clean(s)
