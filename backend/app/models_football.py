"""Football domain models, deliberately independent from the LoL data model."""

from datetime import UTC, datetime
from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class FootballCompetition(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    source_competition_id: str = Field(index=True)
    code: Optional[str] = Field(default=None, index=True)
    name: str
    country: Optional[str] = None
    season: Optional[str] = Field(default=None, index=True)
    active: bool = True
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class FootballTeam(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    source_team_id: str = Field(index=True)
    name: str = Field(index=True)
    short_name: Optional[str] = None
    country: Optional[str] = None
    crest_url: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class FootballPlayer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    source_player_id: str = Field(index=True)
    name: str = Field(index=True)
    position: Optional[str] = None
    nationality: Optional[str] = None
    team_id: Optional[int] = Field(
        default=None, foreign_key="footballteam.id", index=True
    )
    updated_at: datetime = Field(default_factory=_now)


class FootballMatchEvent(SQLModel, table=True):
    """A fixture or completed match; score fields are null until available."""

    id: Optional[int] = Field(default=None, primary_key=True)
    match_key: str = Field(index=True, unique=True)
    source_name: str = Field(index=True)
    source_match_id: str = Field(index=True)
    competition_id: Optional[int] = Field(
        default=None, foreign_key="footballcompetition.id", index=True
    )
    competition_name: Optional[str] = Field(default=None, index=True)
    season: Optional[str] = None
    home_team_id: Optional[int] = Field(
        default=None, foreign_key="footballteam.id", index=True
    )
    away_team_id: Optional[int] = Field(
        default=None, foreign_key="footballteam.id", index=True
    )
    home_team_name: str = Field(index=True)
    away_team_name: str = Field(index=True)
    start_time_utc: datetime = Field(index=True)
    status: str = Field(default="scheduled", index=True)
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    venue: Optional[str] = None
    source_url: Optional[str] = None
    observed_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class FootballTeamMatchStat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_event_id: int = Field(foreign_key="footballmatchevent.id", index=True)
    team_id: Optional[int] = Field(
        default=None, foreign_key="footballteam.id", index=True
    )
    team_name: str = Field(index=True)
    goals: Optional[int] = None
    expected_goals: Optional[float] = None
    possession_pct: Optional[float] = None
    shots: Optional[int] = None
    shots_on_target: Optional[int] = None
    corners: Optional[int] = None
    fouls: Optional[int] = None
    offsides: Optional[int] = None
    yellow_cards: Optional[int] = None
    red_cards: Optional[int] = None
    created_at: datetime = Field(default_factory=_now)


class FootballPlayerMatchStat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    match_event_id: int = Field(foreign_key="footballmatchevent.id", index=True)
    player_id: Optional[int] = Field(
        default=None, foreign_key="footballplayer.id", index=True
    )
    player_name: str = Field(index=True)
    team_id: Optional[int] = Field(
        default=None, foreign_key="footballteam.id", index=True
    )
    minutes_played: Optional[int] = None
    goals: Optional[int] = None
    assists: Optional[int] = None
    shots: Optional[int] = None
    expected_goals: Optional[float] = None
    expected_assists: Optional[float] = None
    yellow_cards: Optional[int] = None
    red_cards: Optional[int] = None
    created_at: datetime = Field(default_factory=_now)


class FootballMatchStatisticsReadModel(SQLModel, table=True):
    """Cached football-specific detail payload, rebuilt after imports."""

    id: Optional[int] = Field(default=None, primary_key=True)
    match_key: str = Field(index=True, unique=True)
    input_fingerprint: str = Field(default="", index=True)
    status: str = Field(default="pending", index=True)
    payload_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    coverage_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    computed_at: Optional[datetime] = None
    updated_at: datetime = Field(default_factory=_now)
