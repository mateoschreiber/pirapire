from datetime import UTC, datetime

from sqlmodel import Session, select

from app.database import engine
from app.models_aposta import CaptureSnapshot
from app.models_imports import ImportedOdds, ManualImportBatch
from app.services.aposta_snapshot import activate_snapshots, run_migrations, snapshot_invariant_violations
from app.services.event_identity import event_key_for, upsert_event
from app.utils.datetime_utils import event_time_display


def _row(kickoff: datetime, **extra):
    row = {
        "source": "aposta_la", "sport": "football", "competition": "Mundial",
        "team_a": "Argentina", "team_b": "España", "event_date": kickoff,
        "raw_kickoff_text": "Mañana 00:01", "market_text": "Ganador",
        "selection": "home",
    }
    row.update(extra)
    return row


def test_derived_key_keeps_same_event_and_separates_dates():
    first = event_key_for(source="aposta_la", source_event_id=None, sport="football", team_a="Argentina", team_b="España", competition="Mundial", kickoff_utc=datetime(2026, 7, 11, 3, 1, tzinfo=UTC))
    second = event_key_for(source="aposta_la", source_event_id=None, sport="football", team_a="Argentina", team_b="España", competition="Mundial", kickoff_utc=datetime(2026, 7, 12, 3, 1, tzinfo=UTC))
    assert first != second
    assert first == event_key_for(source="APOSTA_LA", source_event_id=None, sport="football", team_a="ARGENTINA", team_b="espana", competition="Mundial", kickoff_utc=datetime(2026, 7, 11, 3, 1, tzinfo=UTC))


def test_native_provider_event_key_is_stable_after_upsert():
    with Session(engine) as session:
        snapshot = CaptureSnapshot(source="phase2_test", raw_hash="native-stable")
        session.add(snapshot)
        session.commit()
        session.refresh(snapshot)
        first = upsert_event(session, _row(datetime(2026, 7, 11, 8, tzinfo=UTC), source="kambi", source_event_id="12345"), snapshot.id)
        second = upsert_event(session, _row(datetime(2026, 7, 11, 8, tzinfo=UTC), source="kambi", source_event_id="12345", competition="Worlds"), snapshot.id)
        assert first.id == second.id
        assert first.event_key == second.event_key


def test_snapshots_switch_current_without_deleting_history():
    with Session(engine) as session:
        batch = ManualImportBatch(sport="football", import_type="phase2-test")
        one = CaptureSnapshot(source="phase2_snapshot_test", raw_hash="one", status="success")
        two = CaptureSnapshot(source="phase2_snapshot_test", raw_hash="two", status="success")
        session.add(batch)
        session.add(one)
        session.add(two)
        session.commit()
        session.refresh(batch)
        session.refresh(one)
        session.refresh(two)
        odds = []
        for snapshot, price in ((one, 1.5), (two, 1.7)):
            odd = ImportedOdds(batch_id=batch.id, sport="football", market_text="Ganador", odds_decimal=price, normalized_key=f"phase2-{snapshot.id}", source_name="aposta_la", capture_snapshot_id=snapshot.id, event_key="evt_phase2_snapshot", is_current=False)
            session.add(odd)
            odds.append(odd)
        session.commit()
        activate_snapshots(session, [one.id])
        assert session.get(ImportedOdds, odds[0].id).is_current is True
        activate_snapshots(session, [two.id])
        assert session.get(ImportedOdds, odds[0].id).is_current is False
        assert session.get(ImportedOdds, odds[1].id).is_current is True
        assert len(session.exec(select(ImportedOdds).where(ImportedOdds.event_key == "evt_phase2_snapshot")).all()) == 2


def test_timezone_single_formatter_for_kambi_utc():
    assert event_time_display(datetime(2026, 7, 11, 8, tzinfo=UTC), "confirmed_source_utc") == "11/07 05:00 PY"


def test_phase2_migration_is_idempotent():
    run_migrations(engine)
    run_migrations(engine)


def test_active_odds_obey_snapshot_invariant():
    with Session(engine) as session:
        assert snapshot_invariant_violations(session)["duplicate_current_feeds"] == 0
