from datetime import datetime
from typing import List, Optional

from sqlmodel import SQLModel


class SportCreate(SQLModel):
    name: str
    slug: str


class TeamCreate(SQLModel):
    sport_id: int
    name: str
    short_name: Optional[str] = None


class MatchCreate(SQLModel):
    sport_id: int
    team_a_id: int
    team_b_id: int
    competition: Optional[str] = None
    start_time: Optional[datetime] = None
    status: str = "scheduled"


class OddsAnalyzeRequest(SQLModel):
    odds_decimal: float
    model_probability: Optional[float] = None
    match_id: Optional[int] = None
    market: str = "1x2"
    line: Optional[float] = None
    selection: str = "home"
    bookmaker: Optional[str] = None
    stake: float = 1.0
    persist: bool = False
    # Fase 3: save analysis to PredictionHistory
    save: bool = False
    sport: Optional[str] = None
    match_label: Optional[str] = None
    market_code: Optional[str] = None
    market_text: Optional[str] = None


class OddsAnalyzeResponse(SQLModel):
    odds_decimal: float
    implied_probability: float
    model_probability: float
    fair_odds: float
    expected_value: float
    risk_label: str
    prediction_id: Optional[int] = None


class ComboLeg(SQLModel):
    probability: float
    odds_decimal: Optional[float] = None
    market_code: Optional[str] = None
    market_text: Optional[str] = None
    line: Optional[float] = None
    selection: Optional[str] = None


class ComboAnalyzeRequest(SQLModel):
    legs: List[ComboLeg]
    offered_odds: Optional[float] = None
    stake: float = 1.0
    # Fase 3: save analysis to ComboHistory
    save: bool = False
    name: Optional[str] = None
    sport: Optional[str] = None


class ComboAnalyzeResponse(SQLModel):
    combo_probability: float
    combo_fair_odds: float
    offered_odds: Optional[float] = None
    expected_value: Optional[float] = None
    risk_label: str
    legs: int
    combo_id: Optional[int] = None
