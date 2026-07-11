from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class ManualImportBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sport: str = Field(index=True)
    import_type: str = Field(index=True)
    filename: Optional[str] = None
    original_filename: Optional[str] = None
    status: str = "pending"
    created_at: datetime = Field(default_factory=_now)
    finished_at: Optional[datetime] = None
    total_rows: int = 0
    imported_rows: int = 0
    skipped_rows: int = 0
    error_rows: int = 0
    message: Optional[str] = None


class ManualImportError(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="manualimportbatch.id", index=True)
    row_number: int
    level: str = "error"
    message: str
    raw_row_json: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class ImportedOdds(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: int = Field(foreign_key="manualimportbatch.id", index=True)
    sport: str = Field(index=True)
    bookmaker: Optional[str] = None
    competition: Optional[str] = None
    event_date: Optional[datetime] = None
    team_a: Optional[str] = None
    team_b: Optional[str] = None
    market_text: str
    market_id: Optional[int] = Field(
        default=None, foreign_key="marketcatalog.id", index=True
    )
    market_code: Optional[str] = None
    line: Optional[float] = None
    selection: Optional[str] = None
    odds_decimal: float
    normalized_key: str = Field(index=True)
    source_name: str = "imported"
    created_at: datetime = Field(default_factory=_now)

    # Snapshot + matching fields (Phase 2+)
    is_current: bool = True
    is_matched: bool = False
    match_confidence: Optional[float] = None
    matched_event_id: Optional[int] = None
    matched_event_type: Optional[str] = None
    market_mapping_status: Optional[str] = None
    snapshot_id: Optional[int] = None
    captured_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    event_date_sort: Optional[str] = None
    event_date_raw: Optional[str] = None
    event_time_status: str = "unconfirmed"


    # Canonical capture graph. Old batch/id fields remain for compatibility.
    source_event_id: Optional[str] = Field(default=None, index=True)
    event_key: Optional[str] = Field(default=None, index=True)
    raw_kickoff_text: Optional[str] = None
    kickoff_utc: Optional[datetime] = Field(default=None, index=True)
    source_market_id: Optional[str] = Field(default=None, index=True)
    source_outcome_id: Optional[str] = Field(default=None, index=True)
    capture_snapshot_id: Optional[int] = Field(default=None, index=True)
    canonical_event_id: Optional[int] = Field(default=None, index=True)
    canonical_market_id: Optional[int] = Field(default=None, index=True)
    canonical_outcome_id: Optional[int] = Field(default=None, index=True)
