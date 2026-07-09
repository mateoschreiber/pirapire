from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class PredictionHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sport: Optional[str] = None
    match_label: Optional[str] = None
    market_id: Optional[int] = Field(default=None, foreign_key="marketcatalog.id", index=True)
    market_code: Optional[str] = None
    market_text: Optional[str] = None
    line: Optional[float] = None
    selection: Optional[str] = None
    odds_decimal: float
    model_probability: Optional[float] = None
    implied_probability: float
    fair_odds: float
    expected_value: float
    risk_label: str
    source_context_json: Optional[str] = None
    status: str = "pending"
    result: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    settled_at: Optional[datetime] = None


class ComboHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sport: Optional[str] = None
    name: Optional[str] = None
    offered_odds: Optional[float] = None
    model_probability: Optional[float] = None
    fair_odds: float
    expected_value: Optional[float] = None
    risk_label: str
    status: str = "pending"
    result: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    settled_at: Optional[datetime] = None


class ComboLegHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    combo_id: int = Field(foreign_key="combohistory.id", index=True)
    market_code: Optional[str] = None
    market_text: Optional[str] = None
    line: Optional[float] = None
    selection: Optional[str] = None
    odds_decimal: Optional[float] = None
    model_probability: float
    implied_probability: float
    risk_label: Optional[str] = None
    leg_order: int = 1
