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

class FootballPlayer(SQLModel, table=True):
    __tablename__ = "footballplayer"
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    source_id: Optional[str] = Field(index=True)
    name: str = Field(index=True)
    position: Optional[str] = None
    shirt_number: Optional[int] = None
    date_of_birth: Optional[str] = None
    nationality: Optional[str] = None
    team_id: Optional[int] = Field(default=None, foreign_key="footballteam.id", index=True)
    team_name: Optional[str] = None
    source_key: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now)
    updated_at: Optional[datetime] = None


class FootballEntityMetadata(SQLModel, table=True):
    """Provenance for metadata supplied by a lower-priority fallback."""

    id: Optional[int] = Field(default=None, primary_key=True)
    entity_type: str = Field(index=True)
    internal_id: int = Field(index=True)
    source_name: str = Field(index=True)
    source_external_id: str = Field(index=True)
    canonical_name: Optional[str] = None
    aliases_json: Optional[str] = None
    image_url: Optional[str] = None
    sport: Optional[str] = None
    fallback_used: bool = True
    retrieved_at: datetime = Field(default_factory=_now)


class FootballFixtureStat(SQLModel, table=True):
    """Per-team statistics for a resolved fixture. Null-preserving evidence.

    One row per (provider, fixture_id, team side). Missing values stay null;
    zeros are only stored when the provider explicitly published a zero.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)
    fixture_id: str = Field(index=True)
    team_side: str = Field(index=True)
    team_external_id: Optional[str] = Field(default=None, index=True)
    team_name: Optional[str] = None
    opponent_name: Optional[str] = None
    competition_name: Optional[str] = None
    match_type: Optional[str] = None
    season: Optional[str] = None
    kickoff_utc: Optional[datetime] = Field(default=None, index=True)
    match_status: Optional[str] = None
    is_home: Optional[bool] = None
    goals_for: Optional[int] = None
    goals_against: Optional[int] = None
    ht_goals_for: Optional[int] = None
    ht_goals_against: Optional[int] = None
    result: Optional[str] = None
    corners: Optional[int] = None
    shots_total: Optional[int] = None
    shots_on_target: Optional[int] = None
    fouls: Optional[int] = None
    yellow_cards: Optional[int] = None
    red_cards: Optional[int] = None
    penalties_scored: Optional[int] = None
    penalties_missed: Optional[int] = None
    penalties_awarded: Optional[int] = None
    stats_present: bool = False
    events_present: bool = False
    source_external_id: Optional[str] = Field(default=None, index=True)
    source_key: str = Field(index=True)
    # Phase 4B2 data-quality fields.
    source: Optional[str] = Field(default=None, index=True)
    source_url: Optional[str] = None
    source_id: Optional[str] = Field(default=None, index=True)
    observed_at: Optional[datetime] = None
    data_as_of: Optional[datetime] = None
    freshness_class: Optional[str] = Field(default=None, index=True)
    eligible_for_last_n: bool = False
    # candidate_last_n marks rows that belonged to the best available window
    # even if not eligible now (e.g. stale). Never presented as current window.
    candidate_last_n: bool = False
    fetched_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class FootballFixturePlayerStat(SQLModel, table=True):
    """Per-player, per-fixture detail (fouls, cards) as null-preserving evidence."""

    id: Optional[int] = Field(default=None, primary_key=True)
    provider: str = Field(index=True)
    fixture_id: str = Field(index=True)
    team_name: Optional[str] = Field(default=None, index=True)
    player_external_id: Optional[str] = Field(default=None, index=True)
    player_name: Optional[str] = Field(default=None, index=True)
    fouls_committed: Optional[int] = None
    fouls_drawn: Optional[int] = None
    yellow_cards: Optional[int] = None
    red_cards: Optional[int] = None
    shots_total: Optional[int] = None
    shots_on_target: Optional[int] = None
    penalties_scored: Optional[int] = None
    penalties_missed: Optional[int] = None
    source_key: str = Field(index=True)
    source: Optional[str] = Field(default=None, index=True)
    source_id: Optional[str] = Field(default=None, index=True)
    observed_at: Optional[datetime] = None
    freshness_class: Optional[str] = Field(default=None, index=True)
    eligible_for_last_n: bool = False
    fetched_at: datetime = Field(default_factory=_now)


class EventTeamHistoryWindow(SQLModel, table=True):
    """Per-event, per-team strict history window (Phase 4B41).

    Each row is one of the 10 FINISHED fixtures used for a given Aposta event
    and team, with kickoff_utc strictly before the event kickoff (cutoff_utc).
    The anchor fixture (the event's own match) is never included here.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    event_key: str = Field(index=True)
    team: str = Field(index=True)
    fixture_source_id: str = Field(index=True)
    rank: int = Field(index=True)
    cutoff_utc: datetime
    opponent: Optional[str] = None
    kickoff_utc: Optional[datetime] = Field(default=None, index=True)
    provider: str = "fresh_football"
    source_key: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)
