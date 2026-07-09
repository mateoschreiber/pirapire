from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class Sport(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    slug: str = Field(index=True, unique=True)


class Team(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sport_id: int = Field(foreign_key="sport.id", index=True)
    name: str
    short_name: Optional[str] = None


class Match(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    sport_id: int = Field(foreign_key="sport.id", index=True)
    team_a_id: int = Field(foreign_key="team.id")
    team_b_id: int = Field(foreign_key="team.id")
    competition: Optional[str] = None
    start_time: Optional[datetime] = None
    status: str = "scheduled"


class OddsSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    market: str
    line: Optional[float] = None
    selection: str
    odds_decimal: float
    bookmaker: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Prediction(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_id: int = Field(foreign_key="match.id", index=True)
    market: str
    line: Optional[float] = None
    selection: str
    odds_decimal: float
    implied_probability: float
    model_probability: float
    fair_odds: float
    expected_value: float
    risk_label: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
