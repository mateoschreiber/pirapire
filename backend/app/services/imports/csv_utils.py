"""Shared helpers for CSV importers."""

import csv
import io
import json
from datetime import UTC, datetime

from sqlmodel import Session

from ...models_imports import ManualImportBatch, ManualImportError


def read_rows(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError("CSV file has no headers")
    return list(reader)


def validate_required(columns: dict[str, str | None], row: dict, row_num: int):
    """Check required columns are present (accept blank-only as missing)."""
    missing = [c for c, h in columns.items() if h and (row.get(h) or "").strip() == ""]
    if missing:
        raise ValueError(f"row {row_num}: missing required field(s) {missing}")


def safe_float(value: str | None) -> float | None:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    return float(v)


def safe_int(value: str | None) -> int | None:
    if value is None:
        return None
    v = value.strip()
    if not v:
        return None
    return int(v)


def parse_event_date(value: str | None) -> datetime | None:
    if not value:
        return None
    v = value.strip()
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(v, fmt)
        except ValueError:
            continue
    return None


def normalise_sport(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    if v in ("football", "futbol", "fútbol", "soccer"):
        return "football"
    if v in ("lol", "league of legends", "league of legends"):
        return "lol"
    return v


def log_import_error(
    session: Session, batch: ManualImportBatch, row_num: int, message: str, raw_row: dict = None, level: str = "error"
) -> None:
    batch.error_rows = (batch.error_rows or 0) + 1
    session.add(
        ManualImportError(
            batch_id=batch.id,
            row_number=row_num,
            level=level,
            message=message,
            raw_row_json=json.dumps(raw_row, default=str) if raw_row else None,
        )
    )
    session.add(batch)
    session.commit()


def finish_batch(session: Session, batch: ManualImportBatch, status: str, message: str = None) -> ManualImportBatch:
    batch.status = status
    batch.finished_at = datetime.now(UTC)
    batch.total_rows = (batch.imported_rows or 0) + (batch.skipped_rows or 0) + (batch.error_rows or 0)
    if message:
        batch.message = message
    session.add(batch)
    session.commit()
    session.refresh(batch)
    return batch


def parse_game_length_seconds(value: str | None) -> int | None:
    if not value:
        return None
    v = value.strip()
    if not v:
        return None
    if ":" in v:
        parts = v.split(":")
        try:
            return int(parts[0]) * 60 + int(parts[1])
        except (ValueError, IndexError):
            return None
    try:
        return int(float(v))
    except ValueError:
        return None


def safe_bool(value: str | None) -> bool | None:
    if value is None:
        return None
    v = value.strip().lower()
    if v in ("1", "true", "yes", "y"):
        return True
    if v in ("0", "false", "no", "n"):
        return False
    return None


def col(row: dict, normalised_header: str) -> str | None:
    for key in row:
        if key.strip().lower() == normalised_header:
            return row[key]
    return None


def normalise_selection(value: str | None) -> str | None:
    if not value:
        return None
    v = value.strip().lower()
    mapping = {
        "over": "over",
        "más": "over",
        "mas": "over",
        "+": "over",
        "under": "under",
        "menos": "under",
        "-": "under",
        "home": "home",
        "local": "home",
        "away": "away",
        "visitante": "away",
        "draw": "draw",
        "empate": "draw",
        "yes": "yes",
        "si": "yes",
        "sí": "yes",
        "no": "no",
        "1": "home",
        "2": "away",
        "x": "draw",
    }
    return mapping.get(v, v)
