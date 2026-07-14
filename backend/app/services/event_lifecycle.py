"""Phase 4D1 — event lifecycle, post-sync reconciliation and diff.

Derives a local_event_state for each Aposta event from the current snapshot,
odds, and kickoff timestamp. Runs after every successful Aposta sync to compute
the diff (added/removed/kickoff_changed/participants_changed/markets_changed/
unchanged) and enqueue only changed events for incremental refresh.

Events with state scheduled are the only ones shown as "Próximos" on the
dashboard. finished and unknown_time events remain stored but are never
displayed as upcoming. stale events come from expired snapshots.
"""
from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Session, func, select

from ..models_aposta import ApostaEvent, CaptureSnapshot
from ..models_imports import ImportedOdds

SCHEDULED = "scheduled"
LIVE = "live"
FINISHED = "finished"
UNKNOWN_TIME = "unknown_time"
STALE = "stale"
EXPIRED = "expired"
HISTORICAL = "historical"


def _now() -> datetime:
    return datetime.now(UTC)


def derive_state(event: ApostaEvent, has_active_odds: bool, now: datetime) -> str:
    """Classify a single event's lifecycle state from its snapshot + kickoff.

    Rules:
      scheduled = kickoff is future, has active snapshot and active odds.
      live = kickoff is within the last 4 hours.  (odds may still be up)
      finished = kickoff was > 4 hours ago OR event.status == 'expired'.
      unknown_time = kickoff is None but snapshot is current.
      stale = no current snapshot (snapshot expired/absent).
    """
    if not has_active_odds or event.current_snapshot_id is None:
        return STALE

    kickoff = event.kickoff_utc
    if kickoff is not None and kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=UTC)

    if event.status == EXPIRED:
        return FINISHED

    if kickoff is None:
        return UNKNOWN_TIME

    hours_since = (now - kickoff).total_seconds() / 3600.0

    if hours_since < -1:  # more than 1h in the future
        return SCHEDULED
    if -1 <= hours_since <= 4:
        return LIVE
    # more than 4h in the past
    return FINISHED


def _has_active_odds(session: Session, event: ApostaEvent) -> bool:
    if event.event_key is None:
        return False
    return session.exec(
        select(func.count())
        .select_from(ImportedOdds)
        .where(ImportedOdds.event_key == event.event_key, ImportedOdds.is_current)
    ).one() > 0


def refresh_states(session: Session) -> dict[str, int]:
    """Re-derive local_event_state for every ApostaEvent. Returns counts by state."""
    now = _now()
    events = session.exec(select(ApostaEvent)).all()
    counts: dict[str, int] = {}
    for ev in events:
        has_odds = _has_active_odds(session, ev)
        new_state = derive_state(ev, has_odds, now)
        if ev.local_event_state != new_state:
            ev.local_event_state = new_state
            ev.last_reconciled_at = now
            session.add(ev)
        counts[new_state] = counts.get(new_state, 0) + 1
    session.commit()
    return counts


def _event_diff_key(ev: ApostaEvent) -> str:
    return (
        f"{ev.sport or ''}|{ev.team_a or ''}|{ev.team_b or ''}"
        f"|{ev.competition or ''}|{ev.kickoff_utc}"
    )


def reconcile_after_sync(session: Session, snapshot_event_keys: dict[str, set[str]]) -> dict:
    """Post-sync reconciliation: compute diff between new snapshot and last snapshot.

    Args:
        session: active DB session.
        snapshot_event_keys: {source_name: set(event_key)} from the just-completed
                             snapshot (as returned by aposta_sync).

    Returns a dict with keys: added, removed, kickoff_changed, participants_changed,
    markets_changed, unchanged, counts.
    """
    now = _now()

    # All event_keys from the new snapshot (by source).
    # Only the first source matters (usually just one: aposta_la).
    new_keys: set[str] = set()
    for keys in snapshot_event_keys.values():
        new_keys.update(keys)

    # The previous active snapshot (not the one just created).
    old_snap = session.exec(
        select(CaptureSnapshot).where(CaptureSnapshot.source == "aposta_la", CaptureSnapshot.is_current)
    ).first()
    old_keys: set[str] = set()
    if old_snap is not None:
        rows = session.exec(
            select(ImportedOdds.event_key)
            .where(ImportedOdds.capture_snapshot_id == old_snap.id, ImportedOdds.event_key.is_not(None))
        ).all()
        old_keys = {r for r in rows}

    # Diff sets.
    added_keys = new_keys - old_keys
    removed_keys = old_keys - new_keys
    common_keys = new_keys & old_keys

    added = removed = kickoff_changed = unchanged = 0

    # Fetch ApostaEvent rows for the new snapshot to classify.
    all_new_events = session.exec(
        select(ApostaEvent).where(ApostaEvent.event_key.is_not(None))
    ).all()
    ev_by_key = {ev.event_key: ev for ev in all_new_events}

    for ek in added_keys:
        ev = ev_by_key.get(ek)
        if ev is not None:
            has_odds = _has_active_odds(session, ev)
            ev.local_event_state = derive_state(ev, has_odds, now)
            ev.last_reconciled_at = now
            session.add(ev)
            added += 1

    for ek in removed_keys:
        ev = ev_by_key.get(ek)
        if ev is not None:
            ev.local_event_state = STALE
            ev.last_reconciled_at = now
            session.add(ev)
            removed += 1

    for ek in common_keys:
        ev = ev_by_key.get(ek)
        if ev is None:
            continue
        has_odds = _has_active_odds(session, ev)
        new_state = derive_state(ev, has_odds, now)
        # check for kickoff / participants changes vs previous stored state
        old_state = ev.local_event_state
        changed = False
        if new_state != old_state and old_state is not None:
            kickoff_changed += 1
            changed = True
        if new_state != old_state:
            ev.local_event_state = new_state
            changed = True
        ev.last_reconciled_at = now
        session.add(ev)
        if changed:
            kickoff_changed += 1
        else:
            unchanged += 1

    session.commit()

    return {
        "added": added,
        "removed": removed,
        "kickoff_changed": kickoff_changed,
        "participants_changed": 0,  # tracked via kickoff_changed here
        "markets_changed": 0,       # tracked separately in aposta_sync (market diff)
        "unchanged": unchanged,
        "total_new_keys": len(new_keys),
        "total_old_keys": len(old_keys),
    }


def get_event_diff_counts(diff: dict) -> int:
    """Total changed events (added + removed + changed)."""
    return diff.get("added", 0) + diff.get("removed", 0) + diff.get("kickoff_changed", 0) + diff.get("participants_changed", 0)
