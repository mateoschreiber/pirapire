from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class RecommendationRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    mode: str = "probability"
    sport: Optional[str] = None
    status: str = "pending"
    started_at: datetime = Field(default_factory=_now)
    finished_at: Optional[datetime] = None
    total_candidates: int = 0
    total_recommendations: int = 0
    message: Optional[str] = None


class BetRecommendation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="recommendationrun.id", index=True)
    sport: Optional[str] = Field(default=None, index=True)
    event_label: Optional[str] = None
    market_id: Optional[int] = None
    market_code: Optional[str] = None
    market_text: Optional[str] = None
    selection_text: Optional[str] = None
    line: Optional[float] = None
    odds_decimal: float
    implied_probability: float
    model_probability: float
    fair_odds: float
    expected_value: float
    probability_score: float = 0.0
    profit_score: float = 0.0
    odds_score: float = 0.0
    balanced_score: float = 0.0
    rank_score: float = 0.0
    rank_mode: str = "probability"
    risk_label: Optional[str] = None
    coverage_status: Optional[str] = None
    source_context_json: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class ComboRecommendation(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="recommendationrun.id", index=True)
    sport: Optional[str] = None
    name: Optional[str] = None
    legs_count: int = 0
    offered_odds: Optional[float] = None
    model_probability: float = 0.0
    fair_odds: float = 0.0
    expected_value: Optional[float] = None
    probability_score: float = 0.0
    profit_score: float = 0.0
    odds_score: float = 0.0
    balanced_score: float = 0.0
    rank_score: float = 0.0
    rank_mode: str = "probability"
    risk_label: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class ComboRecommendationLeg(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    combo_id: int = Field(foreign_key="comborecommendation.id", index=True)
    recommendation_id: Optional[int] = None
    leg_order: int = 1
    market_code: Optional[str] = None
    market_text: Optional[str] = None
    selection_text: Optional[str] = None
    line: Optional[float] = None
    odds_decimal: Optional[float] = None
    model_probability: float = 0.0
