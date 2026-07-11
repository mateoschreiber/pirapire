from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from ..config import settings
from ..models_imports import ImportedOdds


def now() -> datetime:
    return datetime.now(UTC)


def run_migrations(engine) -> None:
    conn = sqlite3.connect(settings.database_url.replace("sqlite:///", ""))
    conn.row_factory = sqlite3.Row
    cursor = conn.execute("PRAGMA table_info(importedodds)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    new_columns = {
        "is_current": "BOOLEAN DEFAULT 1",
        "is_matched": "BOOLEAN DEFAULT 0",
        "match_confidence": "REAL",
        "matched_event_id": "INTEGER",
        "matched_event_type": "TEXT",
        "market_mapping_status": "TEXT",
        "snapshot_id": "INTEGER",
        "captured_at": "TIMESTAMP",
        "expires_at": "TIMESTAMP",
        "event_date_sort": "TEXT",
        "event_date_raw": "TEXT",
        "event_time_status": "TEXT NOT NULL DEFAULT 'unconfirmed'",
    }

    for col_name, col_def in new_columns.items():
        if col_name not in existing_columns:
            conn.execute(f"ALTER TABLE importedodds ADD COLUMN {col_name} {col_def}")

    conn.commit()
    conn.close()


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


def set_current_batch(session: Session, batch_id: int) -> None:
    for odd in session.exec(
        select(ImportedOdds).where(
            ImportedOdds.source_name == "aposta_la", ImportedOdds.is_current
        )
    ).all():
        odd.is_current = False
    session.commit()

    for odd in session.exec(
        select(ImportedOdds).where(ImportedOdds.batch_id == batch_id)
    ).all():
        odd.is_current = True
        odd.captured_at = now()
    session.commit()


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
