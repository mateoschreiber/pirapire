from datetime import UTC, datetime
from typing import Optional

from sqlmodel import JSON, Column, Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Static / reference models
# ---------------------------------------------------------------------------
class LolPatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    version: str = Field(index=True)
    region: Optional[str] = None
    source_rank: int = 0
    fallback_used: bool = False
    retrieved_at: datetime = Field(default_factory=_now)


class LolChampion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    champion_key: Optional[str] = Field(default=None, index=True)
    champion_id: str = Field(index=True)
    name: str
    title: Optional[str] = None
    version: Optional[str] = None
    source_rank: int = 0
    fallback_used: bool = False
    retrieved_at: datetime = Field(default_factory=_now)


class LolLeague(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True)
    name: str
    region: Optional[str] = None
    tier: Optional[str] = None
    active: bool = True
    current_name: Optional[str] = None
    legacy_names_json: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class LolTeamAlias(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    canonical_team: str = Field(index=True)
    alias: str = Field(index=True)
    normalized_alias: str = Field(index=True)
    league_slug: Optional[str] = Field(default=None, index=True)
    active_from: Optional[str] = None
    active_to: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class LolLeagueAlias(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    canonical_league: str = Field(index=True)
    alias: str = Field(index=True)
    normalized_alias: str = Field(index=True)
    active_from: Optional[str] = None
    active_to: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Game-level history (kept for stats computation)
# ---------------------------------------------------------------------------
class LolGameHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_name: str = Field(index=True)
    source_game_id: str = Field(index=True)
    year: Optional[int] = Field(default=None, index=True)
    league: Optional[str] = Field(default=None, index=True)
    split: Optional[str] = None
    playoffs: Optional[bool] = None
    date: Optional[str] = None
    patch: Optional[str] = None
    game_number: Optional[int] = None
    game_length_seconds: Optional[int] = None
    blue_team: Optional[str] = None
    red_team: Optional[str] = None
    winner_team: Optional[str] = None
    source_key: str = Field(index=True)
    series_id: Optional[int] = Field(
        default=None, foreign_key="lolseries.id", index=True
    )
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class LolTeamGameStat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: Optional[int] = Field(
        default=None, foreign_key="lolgamehistory.id", index=True
    )
    source_name: str = Field(index=True)
    source_game_id: str = Field(index=True)
    year: Optional[int] = Field(default=None, index=True)
    league: Optional[str] = Field(default=None, index=True)
    date: Optional[str] = None
    patch: Optional[str] = None
    team_name: str = Field(index=True)
    opponent_name: Optional[str] = None
    side: Optional[str] = None
    result: Optional[int] = None
    kills: Optional[int] = None
    deaths: Optional[int] = None
    assists: Optional[int] = None
    team_kills: Optional[int] = None
    team_deaths: Optional[int] = None
    dragons: Optional[int] = None
    barons: Optional[int] = None
    towers: Optional[int] = None
    inhibitors: Optional[int] = None
    game_length_seconds: Optional[int] = None
    first_blood: Optional[bool] = None
    first_tower: Optional[bool] = None
    gold: Optional[int] = None
    final_gold: Optional[int] = None
    earned_gold: Optional[int] = None
    team_id: Optional[int] = Field(default=None, foreign_key="lolteam.id", index=True)
    opponent_team_id: Optional[int] = Field(
        default=None, foreign_key="lolteam.id", index=True
    )
    source_key: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now)


class LolPlayerGameStat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: Optional[int] = Field(
        default=None, foreign_key="lolgamehistory.id", index=True
    )
    source_name: str = Field(index=True)
    source_game_id: str = Field(index=True)
    year: Optional[int] = Field(default=None, index=True)
    league: Optional[str] = Field(default=None, index=True)
    date: Optional[str] = None
    patch: Optional[str] = None
    team_name: Optional[str] = Field(default=None, index=True)
    player_name: Optional[str] = Field(default=None, index=True)
    role: Optional[str] = Field(default=None, index=True)
    champion: Optional[str] = None
    kills: Optional[int] = None
    deaths: Optional[int] = None
    assists: Optional[int] = None
    cs: Optional[int] = None
    damage: Optional[int] = None
    gold: Optional[int] = None
    solo_kills: Optional[int] = None
    final_gold: Optional[int] = None
    team_id: Optional[int] = Field(default=None, foreign_key="lolteam.id", index=True)
    player_id: Optional[int] = Field(
        default=None, foreign_key="lolplayer.id", index=True
    )
    source_key: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now)


class LolDataCoverage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    league: str = Field(index=True)
    year: int = Field(index=True)
    games_count: int = 0
    teams_count: int = 0
    players_count: int = 0
    last_imported_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# Series model (groups games into best-of series)
# ---------------------------------------------------------------------------
class LolSeries(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    series_key: str = Field(index=True, unique=True)
    source_name: str = Field(index=True)
    source_match_id: Optional[str] = Field(default=None, index=True)
    team_a: str = Field(index=True)
    team_b: str = Field(index=True)
    score_a: Optional[int] = None
    score_b: Optional[int] = None
    league: Optional[str] = Field(default=None, index=True)
    tournament: Optional[str] = None
    best_of: Optional[int] = None
    first_game_at: Optional[str] = None
    last_game_at: Optional[str] = None
    game_ids_json: Optional[str] = None
    maps_count: int = 0
    complete: bool = False
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# ---------------------------------------------------------------------------
# New LoL-only models (Phase 1 refactor)
# ---------------------------------------------------------------------------
class LolMatchEvent(SQLModel, table=True):
    """Upcoming or finished professional LoL series."""

    id: Optional[int] = Field(default=None, primary_key=True)
    match_key: str = Field(index=True, unique=True)
    source_name: str = Field(index=True)
    source_match_id: str = Field(index=True)
    league: Optional[str] = Field(default=None, index=True)
    tournament: Optional[str] = None
    team_a: str = Field(index=True)
    team_b: str = Field(index=True)
    start_time_utc: datetime = Field(index=True)
    best_of: Optional[int] = None
    status: str = Field(
        default="scheduled"
    )  # scheduled | live | finished | cancelled | postponed
    source_url: Optional[str] = None
    observed_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class LolOddsSnapshot(SQLModel, table=True):
    """Immutable capture of general winner odds for a series."""

    id: Optional[int] = Field(default=None, primary_key=True)
    match_event_id: Optional[int] = Field(
        default=None, foreign_key="lolmatchevent.id", index=True
    )
    provider: str = Field(index=True)
    captured_at: datetime = Field(default_factory=_now)
    is_current: bool = True
    source_url: Optional[str] = None


class LolTeamOdd(SQLModel, table=True):
    """One team selection inside a snapshot."""

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_id: Optional[int] = Field(
        default=None, foreign_key="loloddssnapshot.id", index=True
    )
    team_name: str = Field(index=True)
    decimal_odds: float


class LolMatchStatisticsReadModel(SQLModel, table=True):
    """Materialised cached statistics payload for a match."""

    id: Optional[int] = Field(default=None, primary_key=True)
    match_key: str = Field(index=True, unique=True)
    input_fingerprint: str
    status: str = "pending"
    payload_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    coverage_json: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    computed_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


# Operational source and stable-identity records.  Existing name fields remain for
# backwards-compatible display; new IDs are used whenever an adapter provides them.
class LolTeam(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    canonical_name: str = Field(index=True, unique=True)
    normalized_name: str = Field(index=True, unique=True)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class LolTeamExternalIdentity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    team_id: int = Field(foreign_key="lolteam.id", index=True)
    source_name: str = Field(index=True)
    external_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now)


class LolPlayer(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    canonical_name: str = Field(index=True)
    normalized_name: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now)


class LolPlayerExternalIdentity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(foreign_key="lolplayer.id", index=True)
    source_name: str = Field(index=True)
    external_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now)


class DataSource(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    code: str = Field(index=True, unique=True)
    display_name: str
    enabled: bool = False
    configured: bool = False
    status: str = "degraded"
    config_json: Optional[str] = None
    last_run_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_error: Optional[str] = None
    last_duration_ms: Optional[int] = None
    records_received: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    coverage: str = "unavailable"
    next_run_at: Optional[datetime] = None


class SourceRun(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_code: str = Field(index=True)
    job: str
    status: str = "running"
    started_at: datetime = Field(default_factory=_now)
    finished_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    records_received: int = 0
    records_inserted: int = 0
    records_updated: int = 0
    records_skipped: int = 0
    error_message: Optional[str] = None
    details_json: Optional[str] = None


class ImportBatch(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    source_code: str = Field(index=True)
    filename: str
    sha256: str = Field(index=True, unique=True)
    status: str = "pending"
    rows_received: int = 0
    games_inserted: int = 0
    teams_inserted: int = 0
    players_inserted: int = 0
    created_at: datetime = Field(default_factory=_now)
    completed_at: Optional[datetime] = None


class ImportError(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    batch_id: Optional[int] = Field(
        default=None, foreign_key="importbatch.id", index=True
    )
    row_number: Optional[int] = None
    reason: str
    raw_json: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)


class WorkerHeartbeat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    worker_name: str = Field(index=True, unique=True)
    status: str = "healthy"
    last_seen_at: datetime = Field(default_factory=_now)
    detail: Optional[str] = None
