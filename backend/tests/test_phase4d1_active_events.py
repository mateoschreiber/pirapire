from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.database import engine
from app.models_aposta import ApostaEvent, RefreshQueue
from app.models_imports import ImportedOdds
from app.services import event_lifecycle as el
from app.services import refresh_queue as rq

MARK = "t4d1"


def _clean(session):
    for r in session.exec(select(RefreshQueue).where(RefreshQueue.event_key.like(f"{MARK}%"))).all():
        session.delete(r)
    for r in session.exec(select(ApostaEvent).where(ApostaEvent.event_key.like(f"{MARK}%"))).all():
        session.delete(r)
    for r in session.exec(select(ImportedOdds).where(ImportedOdds.event_key.like(f"{MARK}%"))).all():
        session.delete(r)
    session.commit()


def _mk_event(session, ek, sport="football", team_a="A", team_b="B", kickoff=None, snap_id=1, has_odds=True):
    ev = ApostaEvent(event_key=ek, sport=sport, team_a=team_a, team_b=team_b,
                     kickoff_utc=kickoff, current_snapshot_id=snap_id, source="aposta_la",
                     local_event_state=None)
    session.add(ev)
    if has_odds:
        session.add(ImportedOdds(batch_id=0, sport=sport, event_key=ek, team_a=team_a,
                                 team_b=team_b, is_current=True, source_name="aposta_la",
                                 market_text="x", odds_decimal=1.5, normalized_key=f"{ek}_0"))
    session.commit()


def test_derive_scheduled_when_future_kickoff_and_has_odds():
    now = datetime.now(UTC)
    ev = ApostaEvent(kickoff_utc=now + timedelta(days=3), current_snapshot_id=1)
    assert el.derive_state(ev, True, now) == "scheduled"


def test_derive_live_when_within_4_hours():
    now = datetime.now(UTC)
    ev = ApostaEvent(kickoff_utc=now - timedelta(hours=2), current_snapshot_id=1)
    assert el.derive_state(ev, True, now) == "live"


def test_derive_finished_when_past_4_hours():
    now = datetime.now(UTC)
    ev = ApostaEvent(kickoff_utc=now - timedelta(hours=5), current_snapshot_id=1)
    assert el.derive_state(ev, True, now) == "finished"


def test_derive_unknown_time_when_no_kickoff():
    now = datetime.now(UTC)
    ev = ApostaEvent(kickoff_utc=None, current_snapshot_id=1)
    assert el.derive_state(ev, True, now) == "unknown_time"


def test_derive_stale_when_no_snapshot():
    now = datetime.now(UTC)
    ev = ApostaEvent(kickoff_utc=now + timedelta(days=1), current_snapshot_id=None)
    assert el.derive_state(ev, True, now) == "stale"


def test_derive_finished_when_expired():
    now = datetime.now(UTC)
    ev = ApostaEvent(kickoff_utc=now + timedelta(days=1), status="expired", current_snapshot_id=1)
    assert el.derive_state(ev, True, now) == "finished"


def test_derive_stale_when_no_active_odds():
    now = datetime.now(UTC)
    ev = ApostaEvent(kickoff_utc=now + timedelta(days=3), current_snapshot_id=1)
    assert el.derive_state(ev, False, now) == "stale"


def test_refresh_states_derives_for_all():
    with Session(engine) as s:
        _clean(s)
        _mk_event(s, f"{MARK}_e1", kickoff=datetime.now(UTC) + timedelta(days=3))
        _mk_event(s, f"{MARK}_e2", kickoff=datetime.now(UTC) - timedelta(hours=6))
        counts = el.refresh_states(s)
        assert counts.get("scheduled", 0) == 1
        assert counts.get("finished", 0) == 1
        _clean(s)


def test_enqueue_and_claim_coalescence():
    with Session(engine) as s:
        _clean(s)
        rq.enqueue(s, f"{MARK}_evA", "football", "added")
        rq.enqueue(s, f"{MARK}_evA", "football", "kickoff_changed")
        assert rq.pending_count(s) == 1
        task = rq.claim_task(s, "w1")
        assert task and task.event_key == f"{MARK}_evA"
        assert task.reason == "kickoff_changed"
        assert task.locked_by == "w1"
        task2 = rq.claim_task(s, "w2")
        assert task2 is None
        rq.release_task(s, f"{MARK}_evA", True)
        assert rq.pending_count(s) == 0
        _clean(s)


def test_claim_releases_expired_locks():
    with Session(engine) as s:
        _clean(s)
        rq.enqueue(s, f"{MARK}_lock1", "lol", "added")
        t = rq.claim_task(s, "stale-worker")
        assert t and t.locked_by == "stale-worker"
        # simulate old lock
        t.locked_at = datetime.now(UTC) - timedelta(seconds=700)
        s.add(t)
        s.commit()
        # new worker should claim it after lock expiry
        t2 = rq.claim_task(s, "new-worker")
        assert t2 and t2.locked_by == "new-worker"
        rq.release_task(s, f"{MARK}_lock1", True)
        _clean(s)
