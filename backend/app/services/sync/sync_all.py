"""Run football + LoL synchronization within a single SourceRun."""

from sqlmodel import Session

from ...models_sources import SourceRun
from . import football_sync, lol_sync


def sync(session: Session, run: SourceRun) -> dict:
    football = football_sync.sync(session, run)
    lol = lol_sync.sync(session, run)

    inserted = football["inserted"] + lol["inserted"]
    updated = football["updated"] + lol["updated"]
    skipped = football["skipped"] + lol["skipped"]

    statuses = {football["status"], lol["status"]}
    if statuses == {"success"}:
        status = "success"
    elif "success" in statuses or "partial" in statuses:
        status = "partial" if "error" in statuses or "partial" in statuses else "success"
    else:
        status = "error"

    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "status": status,
    }
