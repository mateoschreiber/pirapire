from datetime import UTC, datetime
from typing import Optional

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class DataSource(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(index=True, unique=True)
    sport: str = Field(index=True)
    rank: int = 0
    enabled: bool = False
    requires_env: Optional[str] = None
    base_url: Optional[str] = None
    description: Optional[str] = None
    reliability_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class SourceCapability(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_id: int = Field(foreign_key="datasource.id", index=True)
    sport: str = Field(index=True)
    data_type: str = Field(index=True)
    priority: int = 0
    enabled: bool = False
    is_primary: bool = False
    supports_live: bool = False
    supports_history: bool = False
    supports_manual_import: bool = False
    notes: Optional[str] = None


class SourceRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sport: str = Field(index=True)
    source_slug: Optional[str] = Field(default=None, index=True)
    run_type: str = "manual"
    status: str = "pending"
    started_at: datetime = Field(default_factory=_now)
    finished_at: Optional[datetime] = None
    requested_by: Optional[str] = None
    total_records: int = 0
    inserted_records: int = 0
    updated_records: int = 0
    skipped_records: int = 0
    error_count: int = 0
    message: Optional[str] = None


class SourceRunLog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="sourcerun.id", index=True)
    level: str = "info"
    message: str
    created_at: datetime = Field(default_factory=_now)


class RawSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: Optional[int] = Field(default=None, foreign_key="sourcerun.id", index=True)
    source_slug: str = Field(index=True)
    sport: str = Field(index=True)
    data_type: str = Field(index=True)
    external_id: Optional[str] = None
    payload_json: str = ""
    payload_hash: str = Field(index=True)
    retrieved_at: datetime = Field(default_factory=_now)


class NormalizedEntityMap(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sport: str = Field(index=True)
    entity_type: str = Field(index=True)
    source_slug: str = Field(index=True)
    source_external_id: str
    internal_id: Optional[int] = None
    normalized_name: Optional[str] = None
    confidence: float = 1.0
    created_at: datetime = Field(default_factory=_now)


class IntegrationCredential(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint(
            "provider_slug", "credential_name", name="uq_integration_credential"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    provider_slug: str = Field(index=True)
    credential_name: str
    encrypted_value: str
    last4: str
    configured_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
    tested_at: Optional[datetime] = None
    test_status: str = "untested"
    last_used_at: Optional[datetime] = None
    last_error_code: Optional[str] = None


class IntegrationAudit(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    provider_slug: str = Field(index=True)
    operation: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now, index=True)
    result: str
    actor: str
    detail_code: Optional[str] = None
