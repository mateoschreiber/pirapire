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
