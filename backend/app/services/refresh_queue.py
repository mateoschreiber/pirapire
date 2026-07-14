"""Phase 4D1 — coalesced refresh queue per event_key.

Only added, kickoff_changed or participants_changed events are enqueued.
removed events are never enqueued; they are simply inactivated via
local_event_state. Multiple sync cycles before the worker picks up a task
overwrite the same row with the most recent reason and timestamp
(coalescence). A simple instance lock prevents concurrent workers from
picking up the same task.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, delete, func, select

from ..models_aposta import RefreshQueue

LOCK_TTL_SECONDS = 600  # 10 minutes — release abandoned locks.


def _now() -> datetime:
    return datetime.now(UTC)


def enqueue(session: Session, event_key: str, sport: str | None, reason: str) -> None:
    """Upsert a single refresh task. Later sync cycles overwrite the same row."""
    existing = session.exec(
        select(RefreshQueue).where(RefreshQueue.event_key == event_key)
    ).first()
    now = _now()
    if existing:
        existing.reason = reason
        existing.sport = sport
        existing.last_update_at = now
        existing.locked_by = None   # unlock if a pending lock expired
        existing.locked_at = None
        session.add(existing)
    else:
        session.add(RefreshQueue(
            event_key=event_key, sport=sport, reason=reason,
            enqueued_at=now, last_update_at=now,
        ))
    session.commit()


def enqueue_diff(session: Session, diff: dict) -> int:
    """Enqueue all added and changed events from a post-sync diff."""
    enqueued = 0
    # We don't know the individual event_keys from the diff alone;
    # they were already processed in reconcile_after_sync.
    # This function is a placeholder — actual enqueue logic is in the
    # worker's refresh cycle which reads from ApostaEvent state.
    return enqueued


def claim_task(session: Session, worker_id: str) -> RefreshQueue | None:
    """Claim the oldest unlocked task for this worker. Returns None if nothing
    pending or all tasks are locked."""
    now = _now()
    # Release locks older than LOCK_TTL.
    expired = session.exec(
        select(RefreshQueue)
        .where(RefreshQueue.locked_at.is_not(None))
    ).all()
    for t in expired:
        if t.locked_at is not None and (now - (t.locked_at.replace(tzinfo=UTC) if t.locked_at.tzinfo is None else t.locked_at.astimezone(UTC))).total_seconds() > LOCK_TTL_SECONDS:
            t.locked_by = None
            t.locked_at = None
            session.add(t)
    session.commit()

    task = session.exec(
        select(RefreshQueue)
        .where(RefreshQueue.locked_by.is_(None))
        .order_by(RefreshQueue.enqueued_at)
        .limit(1)
    ).first()
    if task is None:
        return None
    task.locked_by = worker_id
    task.locked_at = now
    session.add(task)
    session.commit()
    return task


def release_task(session: Session, event_key: str, success: bool) -> None:
    """Release a task. On success, remove it from the queue (consumed)."""
    if success:
        session.exec(delete(RefreshQueue).where(RefreshQueue.event_key == event_key))
    else:
        task = session.exec(
            select(RefreshQueue).where(RefreshQueue.event_key == event_key)
        ).first()
        if task:
            task.locked_by = None
            task.locked_at = None
            session.add(task)
    session.commit()


def pending_count(session: Session) -> int:
    return session.exec(
        select(func.count())
        .select_from(RefreshQueue)
        .where(RefreshQueue.locked_by.is_(None))
    ).one()


def enqueue_scheduled_events(session: Session) -> int:
    """Scan all scheduled ApostaEvents and enqueue any not yet refreshed."""
    from ..config import settings
    from ..models_aposta import ApostaEvent

    now = _now()
    events = session.exec(
        select(ApostaEvent).where(
            ApostaEvent.local_event_state == "scheduled",
            ApostaEvent.event_key.is_not(None),
        )
    ).all()
    ttl = getattr(settings, "refresh_ttl_hours", 1)
    enqueued = 0
    for ev in events:
        if ev.last_reconciled_at is not None:
            age_h = (now - (ev.last_reconciled_at.replace(tzinfo=UTC) if ev.last_reconciled_at.tzinfo is None else ev.last_reconciled_at.astimezone(UTC))).total_seconds() / 3600.0
            if age_h < ttl:
                continue  # not stale yet
        enqueue(session, ev.event_key, ev.sport or "unknown", "scheduled_refresh")
        enqueued += 1
    return enqueued
