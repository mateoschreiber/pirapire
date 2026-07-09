from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class ApostaSyncRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    status: str = "pending"
    started_at: datetime = Field(default_factory=_now)
    finished_at: Optional[datetime] = None
    requested_by: Optional[str] = None
    captured_responses: int = 0
    parsed_events: int = 0
    parsed_markets: int = 0
    parsed_selections: int = 0
    mapped_markets: int = 0
    unmapped_markets: int = 0
    error_count: int = 0
    message: Optional[str] = None


class ApostaEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sport: Optional[str] = Field(default=None, index=True)
    competition: Optional[str] = None
    event_name: Optional[str] = None
    team_a: Optional[str] = None
    team_b: Optional[str] = None
    start_time: Optional[datetime] = None
    status: Optional[str] = None
    external_id: Optional[str] = Field(default=None, index=True)
    source_url: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ApostaMarket(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    event_id: int = Field(foreign_key="apostaevent.id", index=True)
    market_text: str
    market_code: Optional[str] = None
    market_id: Optional[int] = Field(default=None, foreign_key="marketcatalog.id")
    category: Optional[str] = None
    line: Optional[float] = None
    period: Optional[str] = None
    map_number: Optional[int] = None
    player: Optional[str] = None
    role: Optional[str] = None
    is_mapped: bool = False
    source_status: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class ApostaSelection(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    market_id: int = Field(foreign_key="apostamarket.id", index=True)
    selection_text: str
    selection_normalized: Optional[str] = None
    odds_decimal: float
    implied_probability: Optional[float] = None
    is_active: bool = True
    captured_at: datetime = Field(default_factory=_now)
