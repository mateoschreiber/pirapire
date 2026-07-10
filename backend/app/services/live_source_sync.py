from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from ..config import settings
from ..models_sources import SourceRun
from . import source_runs
from .sync import sync_all


def latest_finished_run(session: Session) -> SourceRun | None:
    return session.exec(
        select(SourceRun)
        .where(SourceRun.sport == 'all', SourceRun.finished_at.is_not(None), SourceRun.status.in_(['success', 'partial']))
        .order_by(SourceRun.finished_at.desc())
    ).first()


def is_stale(session: Session) -> bool:
    last = latest_finished_run(session)
    if last is None or last.finished_at is None:
        return True
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=settings.source_stale_hours)
    return last.finished_at.replace(tzinfo=None) < cutoff


def sync_if_stale(session: Session, force: bool = False) -> dict:
    if not settings.auto_sync_sports_before_recommend:
        return {'status': 'disabled'}
    if not force and not is_stale(session):
        last = latest_finished_run(session)
        return {'status': 'fresh', 'run_id': last.id if last else None}

    run = source_runs.create_run(session, sport='all', source_slug='sync_all', run_type='auto', requested_by='recommendations')
    try:
        result = sync_all.sync(session, run)
        source_runs.finalize(
            session,
            run,
            result['status'],
            inserted=result['inserted'],
            updated=result['updated'],
            skipped=result['skipped'],
        )
        return {
            'status': run.status,
            'run_id': run.id,
            'inserted': run.inserted_records,
            'updated': run.updated_records,
            'skipped': run.skipped_records,
            'errors': run.error_count,
        }
    except Exception as exc:
        source_runs.finalize(session, run, 'error', message=f'{type(exc).__name__}: {exc}')
        return {'status': 'error', 'run_id': run.id, 'message': str(exc)}
