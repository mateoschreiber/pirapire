"""Helpers to create, log and finalize SourceRun records."""

from datetime import UTC, datetime

from sqlmodel import Session

from ..models_sources import SourceRun, SourceRunLog


def create_run(
    session: Session,
    sport: str,
    source_slug: str | None = None,
    run_type: str = "manual",
    requested_by: str | None = None,
) -> SourceRun:
    run = SourceRun(
        sport=sport,
        source_slug=source_slug,
        run_type=run_type,
        status="running",
        started_at=datetime.now(UTC),
        requested_by=requested_by,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def log(session: Session, run: SourceRun, level: str, message: str) -> None:
    session.add(SourceRunLog(run_id=run.id, level=level, message=message))
    if level == "error":
        run.error_count = (run.error_count or 0) + 1
        session.add(run)
    session.commit()


def finalize(
    session: Session,
    run: SourceRun,
    status: str,
    message: str | None = None,
    inserted: int = 0,
    updated: int = 0,
    skipped: int = 0,
) -> SourceRun:
    run.status = status
    run.finished_at = datetime.now(UTC)
    run.inserted_records = inserted
    run.updated_records = updated
    run.skipped_records = skipped
    run.total_records = inserted + updated + skipped
    if message:
        run.message = message
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def resolve_status(inserted: int, updated: int, skipped: int, error_count: int) -> str:
    processed = inserted + updated + skipped
    if error_count == 0:
        return "success"
    if processed > 0:
        return "partial"
    return "error"
