from datetime import UTC, datetime
from typing import Optional

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


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
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class LolTeamGameStat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: Optional[int] = Field(default=None, foreign_key='lolgamehistory.id', index=True)
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
    source_key: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now)


class LolPlayerGameStat(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    game_id: Optional[int] = Field(default=None, foreign_key='lolgamehistory.id', index=True)
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


class RiotPlayerIdentity(SQLModel, table=True):
    """Explicitly confirmed bridge between an internal player and a Riot account."""

    id: Optional[int] = Field(default=None, primary_key=True)
    player_id: int = Field(index=True)
    game_name: str
    tag_line: str
    puuid: Optional[str] = Field(default=None, index=True)
    platform: str = "la2"
    valid_from: datetime = Field(default_factory=_now)
    source: str = "confirmed_manual"
    confirmed: bool = False
    last_verified_at: Optional[datetime] = None


class RiotMatchReference(SQLModel, table=True):
    """Personal/verified Riot match reference, deliberately separate from esports."""

    id: Optional[int] = Field(default=None, primary_key=True)
    identity_id: int = Field(foreign_key="riotplayeridentity.id", index=True)
    match_id: str = Field(index=True, unique=True)
    queue_id: Optional[int] = None
    game_type: Optional[str] = None
    game_mode: Optional[str] = None
    game_started_at: Optional[datetime] = None
    source_name: str = "riot_match_v5"
    match_scope: str = "personal_verified"
    retrieved_at: datetime = Field(default_factory=_now)
