"""Provider contract for fixture, result, event and odds ingestion."""

from abc import ABC, abstractmethod
from datetime import datetime


class FootballSource(ABC):
    slug: str

    @abstractmethod
    def fetch_fixtures(self, start: datetime, end: datetime) -> list[dict]:
        """Return provider fixtures at the transport boundary."""

    @abstractmethod
    def fetch_match_statistics(self, source_match_id: str) -> dict | None:
        """Return raw provider statistics for a completed fixture."""
