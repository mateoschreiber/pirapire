from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models_aposta import ApostaEvent, ApostaMarket, ApostaSelection, ApostaSyncRun

router = APIRouter(prefix="/aposta", tags=["aposta"])

_UNAVAILABLE_MESSAGE = (
    "Aposta.LA browser worker no configurado. Use importacion CSV (/imports/ui) o "
    "habilite el worker opcional (Fase 4B) definiendo APOSTA_BROWSER_WORKER_URL."
)


@router.post("/sync")
def sync(session: Session = Depends(get_session)) -> dict:
    """Manual Aposta.LA sync. In Fase 4A there is no browser worker, so this
    records a run with status 'manual_required' and never touches aposta.la."""
    worker = settings.aposta_browser_worker_url.strip()
    status = "manual_required" if not worker else "unavailable"
    run = ApostaSyncRun(
        status=status,
        finished_at=datetime.now(UTC),
        message=_UNAVAILABLE_MESSAGE,
    )
    session.add(run)
    session.commit()
    session.refresh(run)
    return {
        "run_id": run.id,
        "status": run.status,
        "message": run.message,
        "worker_configured": bool(worker),
    }


@router.get("/status")
def status(session: Session = Depends(get_session)) -> dict:
    last = session.exec(select(ApostaSyncRun).order_by(ApostaSyncRun.id.desc())).first()
    worker = settings.aposta_browser_worker_url.strip()
    return {
        "worker_configured": bool(worker),
        "sync_enabled": settings.aposta_sync_enabled,
        "last_run": last,
        "message": None if worker else _UNAVAILABLE_MESSAGE,
    }


@router.get("/sync-runs")
def sync_runs(limit: int = 50, session: Session = Depends(get_session)) -> list:
    return session.exec(select(ApostaSyncRun).order_by(ApostaSyncRun.id.desc()).limit(limit)).all()


@router.get("/events")
def events(limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(select(ApostaEvent).order_by(ApostaEvent.id.desc()).limit(limit)).all()


@router.get("/markets")
def markets(limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(select(ApostaMarket).order_by(ApostaMarket.id.desc()).limit(limit)).all()


@router.get("/selections")
def selections(limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(select(ApostaSelection).order_by(ApostaSelection.id.desc()).limit(limit)).all()
