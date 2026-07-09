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


class OddsAnalyzeResponse(SQLModel):
    odds_decimal: float
    implied_probability: float
    model_probability: float
    fair_odds: float
    expected_value: float
    risk_label: str


class ComboLeg(SQLModel):
    probability: float
    odds_decimal: Optional[float] = None


class ComboAnalyzeRequest(SQLModel):
    legs: List[ComboLeg]
    offered_odds: Optional[float] = None
    stake: float = 1.0


class ComboAnalyzeResponse(SQLModel):
    combo_probability: float
    combo_fair_odds: float
    offered_odds: Optional[float] = None
    expected_value: Optional[float] = None
    risk_label: str
    legs: int
