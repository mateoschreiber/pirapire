from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session, select

from ..database import get_session
from ..models_imports import (
    ImportedOdds,
    ManualImportBatch,
    ManualImportError,
)
from ..services.imports import aposta_odds_importer, oracles_elixir_importer

router = APIRouter(tags=["imports"])

TEMPLATE_DIR = Path("app/import_templates")


@router.get("/imports/templates/aposta-odds")
def template_aposta():
    path = TEMPLATE_DIR / "aposta_odds_template.csv"
    return FileResponse(path, media_type="text/csv", filename="aposta_odds_template.csv")


@router.get("/imports/templates/oracles-elixir")
def template_oracles():
    path = TEMPLATE_DIR / "oracles_elixir_sample.csv"
    return FileResponse(path, media_type="text/csv", filename="oracles_elixir_sample.csv")


async def _read_csv(file: UploadFile) -> str:
    raw = await file.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("latin-1")


@router.post("/imports/aposta-odds-csv")
async def import_aposta(file: UploadFile = File(...), session: Session = Depends(get_session)) -> dict:
    text = await _read_csv(file)
    batch = ManualImportBatch(
        sport="mixed", import_type="aposta_odds", filename=file.filename,
        original_filename=file.filename, status="running",
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    batch = aposta_odds_importer.import_csv(session, batch, text)
    return _batch_dict(batch)


@router.post("/imports/oracles-elixir-csv")
async def import_oracles(file: UploadFile = File(...), session: Session = Depends(get_session)) -> dict:
    text = await _read_csv(file)
    batch = ManualImportBatch(
        sport="lol", import_type="oracles_elixir", filename=file.filename,
        original_filename=file.filename, status="running",
    )
    session.add(batch)
    session.commit()
    session.refresh(batch)
    batch = oracles_elixir_importer.import_csv(session, batch, text)
    return _batch_dict(batch)


def _batch_dict(b: ManualImportBatch) -> dict:
    return {
        "id": b.id,
        "sport": b.sport,
        "import_type": b.import_type,
        "filename": b.original_filename,
        "status": b.status,
        "total_rows": b.total_rows,
        "imported_rows": b.imported_rows,
        "skipped_rows": b.skipped_rows,
        "error_rows": b.error_rows,
        "message": b.message,
        "created_at": b.created_at,
        "finished_at": b.finished_at,
    }


@router.get("/imports/batches")
def list_batches(limit: int = 50, session: Session = Depends(get_session)) -> list:
    rows = session.exec(
        select(ManualImportBatch).order_by(ManualImportBatch.id.desc()).limit(limit)
    ).all()
    return [_batch_dict(b) for b in rows]


@router.get("/imports/batches/{batch_id}")
def get_batch(batch_id: int, session: Session = Depends(get_session)) -> dict:
    batch = session.get(ManualImportBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="batch not found")
    return _batch_dict(batch)


@router.get("/imports/batches/{batch_id}/errors")
def get_batch_errors(batch_id: int, limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(
        select(ManualImportError)
        .where(ManualImportError.batch_id == batch_id)
        .order_by(ManualImportError.row_number)
        .limit(limit)
    ).all()


@router.get("/odds/imported")
def list_imported_odds(limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(select(ImportedOdds).order_by(ImportedOdds.id.desc()).limit(limit)).all()
