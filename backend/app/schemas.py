from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel


class MatchResponse(BaseModel):
    match_key: str
    source_name: Optional[str] = None
    league: Optional[str] = None
    tournament: Optional[str] = None
    team_a: str
    team_b: str
    start_time_utc: str
    best_of: Optional[int] = None
    status: str
    source_url: Optional[str] = None
    odds_a: Optional[float] = None
    odds_b: Optional[float] = None
    odds_provider: Optional[str] = None
    odds_captured_at: Optional[str] = None


class UpcomingMatch(BaseModel):
    match_key: str
    league: Optional[str] = None
    tournament: Optional[str] = None
    team_a: str
    team_b: str
    start_time_utc: str
    best_of: Optional[int] = None
    status: str
    odds_a: Optional[float] = None
    odds_b: Optional[float] = None
    odds_provider: Optional[str] = None
    odds_captured_at: Optional[str] = None


class UpcomingResponse(BaseModel):
    matches: list[UpcomingMatch]
    count: int
    window_hours: int
    timezone: str


class StatisticsResponse(BaseModel):
    match_key: str
    status: str
    payload: Optional[dict] = None
    coverage: Optional[dict] = None
    computed_at: Optional[str] = None


class OddsImportRequest(BaseModel):
    match_key: str
    team_name: str
    decimal_odds: float
    provider: str = "manual"
    captured_at: Optional[str] = None
