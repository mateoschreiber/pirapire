from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from ..config import settings
from ..models_imports import ImportedOdds
from ..models_aposta import CaptureSnapshot, ApostaEvent


def now() -> datetime:
    return datetime.now(UTC)


def run_migrations(engine) -> None:
    """Expand-only, idempotent SQLite migration for the canonical capture graph."""
    from pathlib import Path
    import shutil

    db_path = settings.database_url.replace("sqlite:///", "", 1)
    if not settings.database_url.startswith("sqlite:///"):
        return
    path = Path(db_path)
    if path.exists():
        # A verified backup is intentionally taken before every schema expansion.
        with sqlite3.connect(path) as check:
            integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
        if integrity != "ok":
            raise RuntimeError(f"SQLite integrity_check failed before migration: {integrity}")
        backup = path.with_name(path.name + ".phase2-pre-migration.bak")
        if not backup.exists():
            shutil.copy2(path, backup)
            with sqlite3.connect(backup) as copied:
                if copied.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                    raise RuntimeError("SQLite migration backup integrity_check failed")

    conn = sqlite3.connect(db_path)
    try:
        existing_columns = {
            row[1] for row in conn.execute("PRAGMA table_info(importedodds)").fetchall()
        }
        new_columns = {
            "is_current": "BOOLEAN DEFAULT 1", "is_matched": "BOOLEAN DEFAULT 0",
            "match_confidence": "REAL", "matched_event_id": "INTEGER",
            "matched_event_type": "TEXT", "market_mapping_status": "TEXT",
            "snapshot_id": "INTEGER", "captured_at": "TIMESTAMP", "expires_at": "TIMESTAMP",
            "event_date_sort": "TEXT", "event_date_raw": "TEXT",
            "event_time_status": "TEXT NOT NULL DEFAULT 'unconfirmed'",
            "source_event_id": "TEXT", "event_key": "TEXT", "raw_kickoff_text": "TEXT",
            "kickoff_utc": "TIMESTAMP", "source_market_id": "TEXT", "source_outcome_id": "TEXT",
            "capture_snapshot_id": "INTEGER", "canonical_event_id": "INTEGER",
            "canonical_market_id": "INTEGER", "canonical_outcome_id": "INTEGER",
        }
        for name, definition in new_columns.items():
            if name not in existing_columns:
                conn.execute(f"ALTER TABLE importedodds ADD COLUMN {name} {definition}")

        event_columns = {row[1] for row in conn.execute("PRAGMA table_info(apostaevent)").fetchall()}
        for name, definition in {
            "source": "TEXT DEFAULT 'aposta_la'", "source_event_id": "TEXT", "event_key": "TEXT",
            "raw_kickoff_text": "TEXT", "kickoff_utc": "TIMESTAMP", "current_snapshot_id": "INTEGER",
            "expires_at": "TIMESTAMP",
        }.items():
            if name not in event_columns:
                conn.execute(f"ALTER TABLE apostaevent ADD COLUMN {name} {definition}")
        market_columns = {row[1] for row in conn.execute("PRAGMA table_info(apostamarket)").fetchall()}
        if "source_market_id" not in market_columns:
            conn.execute("ALTER TABLE apostamarket ADD COLUMN source_market_id TEXT")
        selection_columns = {row[1] for row in conn.execute("PRAGMA table_info(apostaselection)").fetchall()}
        if "source_outcome_id" not in selection_columns:
            conn.execute("ALTER TABLE apostaselection ADD COLUMN source_outcome_id TEXT")

        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_apostaevent_event_key ON apostaevent(event_key) WHERE event_key IS NOT NULL")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_importedodds_event_key_current ON importedodds(event_key, is_current)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_importedodds_capture_snapshot ON importedodds(capture_snapshot_id)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_canonicalmarket_identity ON canonicalmarket(identity_key)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS ux_canonicaloutcome_identity ON canonicaloutcome(identity_key)")
        conn.execute("CREATE INDEX IF NOT EXISTS ix_capturesnapshot_source_current ON capturesnapshot(source, is_current)")
        conn.commit()
    finally:
        conn.close()


def backfill_canonical_identity(session: Session) -> int:
    """Fill identity fields and create canonical events for active legacy odds.

    Historical raw data remains untouched; legacy events are materialized only
    from rows that are still active so public links work before the next sync.
    """
    from .event_identity import event_key_for, utc_datetime

    changed = 0
    rows = session.exec(select(ImportedOdds)).all()
    active_by_key: dict[str, ImportedOdds] = {}
    for row in rows:
        kickoff = utc_datetime(row.event_date)
        if row.event_key is None and kickoff is not None:
            row.event_key = event_key_for(
                source=row.source_name or "aposta_la", source_event_id=row.source_event_id,
                sport=row.sport, team_a=row.team_a, team_b=row.team_b,
                competition=row.competition, kickoff_utc=kickoff,
            )
            row.kickoff_utc = kickoff
            row.raw_kickoff_text = row.event_date_raw
            changed += 1
        if row.is_current and row.event_key:
            active_by_key.setdefault(row.event_key, row)
    session.commit()

    for key, row in active_by_key.items():
        event = session.exec(select(ApostaEvent).where(ApostaEvent.event_key == key)).first()
        if event is None:
            event = ApostaEvent(
                event_key=key, source=row.source_name or "aposta_la",
                source_event_id=row.source_event_id, sport=row.sport,
                competition=row.competition, team_a=row.team_a, team_b=row.team_b,
                event_name=" vs ".join(x for x in (row.team_a, row.team_b) if x),
                start_time=row.kickoff_utc or row.event_date,
                kickoff_utc=row.kickoff_utc or utc_datetime(row.event_date),
                raw_kickoff_text=row.raw_kickoff_text or row.event_date_raw,
                status="active",
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            changed += 1
        if row.canonical_event_id is None:
            row.canonical_event_id = event.id
            session.add(row)
    session.commit()
    return changed


def normalize_datetime(value):
    if value is None:
        return None
    if hasattr(value, "tzinfo") and value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _is_current_odd(odd: ImportedOdds) -> bool:
    if odd.event_date is None:
        return True
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=3)
    event_dt = normalize_datetime(odd.event_date)
    if event_dt is None:
        return True
    return event_dt >= cutoff


def current_odds(session: Session, include_stale: bool = False) -> list[ImportedOdds]:
    query = select(ImportedOdds).where(ImportedOdds.source_name == "aposta_la")
    if not include_stale:
        query = query.where(ImportedOdds.is_current)
    rows = session.exec(query.order_by(ImportedOdds.id.desc())).all()
    return [r for r in rows if _is_current_odd(r)]


def expired_odds(session: Session) -> list[ImportedOdds]:
    rows = session.exec(
        select(ImportedOdds)
        .where(ImportedOdds.source_name == "aposta_la", ImportedOdds.is_current)
        .order_by(ImportedOdds.id.desc())
    ).all()
    return [r for r in rows if not _is_current_odd(r)]


def historical_odds(session: Session) -> list[ImportedOdds]:
    return session.exec(
        select(ImportedOdds)
        .where(ImportedOdds.source_name == "aposta_la")
        .order_by(ImportedOdds.id.desc())
    ).all()


def mark_expired(session: Session) -> int:
    rows = expired_odds(session)
    count = 0
    for row in rows:
        row.is_current = False
        count += 1
    session.commit()
    return count


def activate_snapshots(session: Session, snapshot_ids: list[int]) -> None:
    """Make only the latest successful capture per source current.

    A batch is an import transport detail, never public event identity.
    """
    snapshots = [session.get(CaptureSnapshot, sid) for sid in snapshot_ids]
    snapshots = [snap for snap in snapshots if snap is not None]
    sources = {snap.source for snap in snapshots}
    for source in sources:
        for snap in session.exec(select(CaptureSnapshot).where(CaptureSnapshot.source == source)).all():
            snap.is_current = snap.id in snapshot_ids
            session.add(snap)
        for odd in session.exec(select(ImportedOdds).where(ImportedOdds.source_name == "aposta_la")).all():
            captured = session.get(CaptureSnapshot, odd.capture_snapshot_id)
            if captured and captured.source == source:
                odd.is_current = captured.id in snapshot_ids
                odd.captured_at = captured.finished_at or now()
                session.add(odd)
    session.commit()


def expire_absent_events(session: Session, source: str, active_snapshot_id: int, seen_keys: set[str]) -> int:
    count = 0
    for event in session.exec(select(ApostaEvent).where(ApostaEvent.source == source, ApostaEvent.status == "active")).all():
        if event.event_key not in seen_keys:
            event.status = "expired"
            event.expires_at = now()
            session.add(event)
            count += 1
    session.commit()
    return count


def set_current_batch(session: Session, batch_id: int) -> None:
    """Legacy shim: activate the snapshots produced by this import batch."""
    ids = [r.capture_snapshot_id for r in session.exec(select(ImportedOdds).where(ImportedOdds.batch_id == batch_id)).all() if r.capture_snapshot_id]
    activate_snapshots(session, list(dict.fromkeys(ids)))


def snapshot_summary(session: Session) -> dict:
    total = len(historical_odds(session))
    cur = len(current_odds(session))
    exp = len(expired_odds(session))

    unmatched = len(
        session.exec(
            select(ImportedOdds).where(
                ImportedOdds.source_name == "aposta_la", ~ImportedOdds.is_matched
            )
        ).all()
    )

    unmapped = len(
        set(
            (odd.sport, odd.market_text)
            for odd in session.exec(
                select(ImportedOdds).where(
                    ImportedOdds.source_name == "aposta_la",
                    ImportedOdds.market_id.is_(None),
                    ImportedOdds.market_code.is_(None),
                )
            ).all()
        )
    )

    return {
        "total_historical": total,
        "current": cur,
        "expired": exp,
        "unmatched": unmatched,
        "unmapped_markets": unmapped,
    }
