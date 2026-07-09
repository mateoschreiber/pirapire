from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class FootballCompetition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    source_external_id: str = Field(index=True)
    code: Optional[str] = Field(default=None, index=True)
    name: str
    country: Optional[str] = None
    season: Optional[str] = None
    current: bool = True
    emblem_url: Optional[str] = None
    source_rank: int = 0
    fallback_used: bool = False
    retrieved_at: datetime = Field(default_factory=_now)


class FootballTeam(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    source_external_id: str = Field(index=True)
    name: str
    short_name: Optional[str] = None
    tla: Optional[str] = None
    country: Optional[str] = None
    crest_url: Optional[str] = None
    source_rank: int = 0
    fallback_used: bool = False
    retrieved_at: datetime = Field(default_factory=_now)


class FootballStanding(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    competition_id: Optional[int] = Field(default=None, foreign_key="footballcompetition.id", index=True)
    team_id: Optional[int] = Field(default=None, foreign_key="footballteam.id", index=True)
    season: Optional[str] = None
    position: Optional[int] = None
    played_games: Optional[int] = None
    won: Optional[int] = None
    draw: Optional[int] = None
    lost: Optional[int] = None
    points: Optional[int] = None
    goals_for: Optional[int] = None
    goals_against: Optional[int] = None
    goal_difference: Optional[int] = None
    source_rank: int = 0
    fallback_used: bool = False
    retrieved_at: datetime = Field(default_factory=_now)


class FootballMatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    source_external_id: str = Field(index=True)
    competition_id: Optional[int] = Field(default=None, foreign_key="footballcompetition.id", index=True)
    home_team_id: Optional[int] = Field(default=None, foreign_key="footballteam.id")
    away_team_id: Optional[int] = Field(default=None, foreign_key="footballteam.id")
    start_time: Optional[datetime] = None
    status: Optional[str] = None
    matchday: Optional[int] = None
    stage: Optional[str] = None
    group_name: Optional[str] = None
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    ht_home_score: Optional[int] = None
    ht_away_score: Optional[int] = None
    winner: Optional[str] = None
    source_rank: int = 0
    fallback_used: bool = False
    retrieved_at: datetime = Field(default_factory=_now)
