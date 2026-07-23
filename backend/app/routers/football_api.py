"""HTTP boundary for football dashboards and fixture synchronization."""

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from sqlmodel import Session, select

from ..config import settings
from ..database import engine, get_session
from ..models_football import FootballMatchEvent
from ..models_lol import DataSource, SourceRun

router = APIRouter(prefix="/api/football")
FOOTBALL_PROVIDER_CODES = ("api_football", "football_data")


def _utc_iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _admin(token: str | None = Header(default=None, alias="X-Admin-Token")):
    if not settings.admin_token or token != settings.admin_token:
        raise HTTPException(403, "Administrative authentication required")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _run_football_sync(run_id: int, source_codes: list[str]) -> None:
    started = _now()
    with Session(engine) as session:
        run = session.get(SourceRun, run_id)
        if not run:
            return
        run.status = "running"
        run.started_at = started
        session.add(run)
        session.commit()
        totals = {"received": 0, "inserted": 0, "updated": 0, "skipped": 0}
        errors = []
        for code in source_codes:
            source = session.exec(select(DataSource).where(DataSource.code == code)).first()
            if not source:
                continue
            try:
                from ..services.football.importer import import_fixtures

                result = import_fixtures(session, source)
                finished = _now()
                source.status = "healthy"
                source.last_run_at = finished
                source.last_success_at = finished
                source.last_error = None
                source.records_received = result["received"]
                source.records_inserted = result["inserted"]
                source.records_updated = result["updated"]
                source.records_skipped = result["skipped"]
                source.coverage = "fixtures"
                session.add(source)
                for key in totals:
                    totals[key] += result[key]
                session.commit()
            except Exception as exc:  # Keep a failed provider from blocking another one.
                session.rollback()
                source = session.exec(select(DataSource).where(DataSource.code == code)).first()
                if source:
                    source.status = "degraded"
                    source.last_run_at = _now()
                    source.last_error = str(exc)
                    session.add(source)
                    session.commit()
                errors.append(f"{code}: {exc}")
        finished = _now()
        run = session.get(SourceRun, run_id)
        run.finished_at = finished
        run.duration_ms = int((finished - started).total_seconds() * 1000)
        run.records_received = totals["received"]
        run.records_inserted = totals["inserted"]
        run.records_updated = totals["updated"]
        run.records_skipped = totals["skipped"]
        run.details_json = str(totals)
        run.status = "failed" if errors and not totals["received"] else "success"
        run.error_message = "; ".join(errors) or None
        session.add(run)
        session.commit()


@router.post("/sync", dependencies=[Depends(_admin)])
def synchronize_football(
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
):
    active = session.exec(
        select(SourceRun)
        .where(SourceRun.job == "football_sync")
        .where(SourceRun.status.in_(["queued", "running"]))
        .order_by(SourceRun.id.desc())
    ).first()
    if active:
        return {"run_id": active.id, "status": active.status, "already_running": True}
    sources = session.exec(
        select(DataSource)
        .where(DataSource.code.in_(FOOTBALL_PROVIDER_CODES))
        .where(DataSource.enabled == True)  # noqa: E712
        .where(DataSource.configured == True)  # noqa: E712
    ).all()
    if not sources:
        raise HTTPException(409, "Configure y habilite al menos una API de fútbol en Fuentes")
    run = SourceRun(source_code="football", job="football_sync", status="queued", started_at=_now())
    session.add(run)
    session.commit()
    session.refresh(run)
    background_tasks.add_task(_run_football_sync, run.id, [source.code for source in sources])
    return {"run_id": run.id, "status": "queued", "providers": [source.code for source in sources]}


@router.get("/matches/upcoming")
def upcoming_matches(
    hours: int = Query(default=336, ge=1, le=720),
    session: Session = Depends(get_session),
):
    now = datetime.now(timezone.utc)
    matches = session.exec(
        select(FootballMatchEvent)
        .where(FootballMatchEvent.start_time_utc >= now)
        .where(FootballMatchEvent.start_time_utc <= now + timedelta(hours=hours))
        .where(FootballMatchEvent.status == "scheduled")
        .order_by(FootballMatchEvent.start_time_utc.asc())
    ).all()
    providers = session.exec(
        select(DataSource).where(DataSource.code.in_(FOOTBALL_PROVIDER_CODES))
    ).all()
    active_providers = [provider for provider in providers if provider.enabled and provider.configured]
    source_status = "ready" if matches else "not_configured" if not active_providers else "degraded" if any(provider.status == "degraded" for provider in active_providers) else "empty"
    source_message = next(
        (provider.last_error for provider in active_providers if provider.last_error),
        None,
    )
    return {
        "matches": [
            {
                "match_key": match.match_key,
                "competition": match.competition_name,
                "home_team": match.home_team_name,
                "away_team": match.away_team_name,
                "start_time_utc": _utc_iso(match.start_time_utc),
                "status": match.status,
            }
            for match in matches
        ],
        "count": len(matches),
        "window_hours": hours,
        "timezone": settings.app_timezone,
        "source_status": source_status,
        "source_message": source_message,
    }
