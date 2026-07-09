"""Shared helpers for source connectors."""

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Optional


@dataclass
class SyncCounters:
    inserted: int = 0
    updated: int = 0
    skipped: int = 0

    def add(self, triple: tuple[int, int, int]) -> None:
        i, u, s = triple
        self.inserted += i
        self.updated += u
        self.skipped += s


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def utcnow() -> datetime:
    return datetime.now(UTC)
