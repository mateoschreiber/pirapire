from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class MarketCatalog(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sport: str = Field(index=True)
    market_code: str = Field(index=True)
    display_name: str
    category: Optional[str] = None
    description: Optional[str] = None
    data_requirements_json: Optional[str] = None
    source_status: str = "unsupported"
    risk_level: str = "medium"
    enabled: bool = True
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class MarketAlias(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market_id: int = Field(foreign_key="marketcatalog.id", index=True)
    alias_text: str
    normalized_alias: str = Field(index=True)
    bookmaker: Optional[str] = None
    language: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class MarketSourceRequirement(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market_id: int = Field(foreign_key="marketcatalog.id", index=True)
    required_data_type: str
    preferred_source_slug: Optional[str] = None
    fallback_source_slug: Optional[str] = None
    availability_status: str = "unsupported"
    notes: Optional[str] = None
