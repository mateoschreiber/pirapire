from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models_sources import RawSnapshot, SourceRun, SourceRunLog

router = APIRouter(tags=["source-runs"])


@router.get("/source-runs")
def list_runs(limit: int = 50, session: Session = Depends(get_session)) -> list:
    return session.exec(select(SourceRun).order_by(SourceRun.id.desc()).limit(limit)).all()


@router.get("/source-runs/{run_id}")
def get_run(run_id: int, session: Session = Depends(get_session)) -> SourceRun:
    run = session.get(SourceRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.get("/source-runs/{run_id}/logs")
def get_run_logs(run_id: int, session: Session = Depends(get_session)) -> list:
    return session.exec(
        select(SourceRunLog).where(SourceRunLog.run_id == run_id).order_by(SourceRunLog.id)
    ).all()


@router.get("/raw-snapshots")
def list_snapshots(limit: int = 50, session: Session = Depends(get_session)) -> list:
    rows = session.exec(
        select(RawSnapshot).order_by(RawSnapshot.id.desc()).limit(limit)
    ).all()
    # Return metadata only (omit full payload_json to keep responses small).
    return [
        {
            "id": r.id,
            "run_id": r.run_id,
            "source_slug": r.source_slug,
            "sport": r.sport,
            "data_type": r.data_type,
            "external_id": r.external_id,
            "payload_hash": r.payload_hash,
            "retrieved_at": r.retrieved_at,
        }
        for r in rows
    ]
