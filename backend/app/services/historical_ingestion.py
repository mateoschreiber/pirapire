"""Bounded, idempotent historical-ingestion coordinator (Phase 4B)."""
from __future__ import annotations
from datetime import UTC, datetime
from sqlmodel import Session, select
from ..models_imports import ImportedOdds
from .secret_provider import SecretProvider
from . import source_runs


def active_participants(session: Session) -> dict[str, set[str]]:
    rows = session.exec(select(ImportedOdds).where(ImportedOdds.is_current)).all()
    out = {"football": set(), "lol": set()}
    for row in rows:
        if row.sport in out:
            out[row.sport].update(x for x in (row.team_a, row.team_b) if x)
    return out


def run(session: Session) -> dict:
    """Record a bounded run; providers with no access remain explicitly unconfigured."""
    participants = active_participants(session)
    football_run = source_runs.create_run(session, "football", "historical_ingestion", "scheduled")
    api_key, source = SecretProvider.get_secret("api_football", "api_key", session=session)
    source_runs.finalize(session, football_run, "partial", message=(
        f"participants={len(participants['football'])}; api_football={source}; "
        "no external detail download without configured provider"
    ), skipped=len(participants["football"]))
    lol_run = source_runs.create_run(session, "lol", "historical_ingestion", "scheduled")
    source_runs.finalize(session, lol_run, "partial", message=(
        f"participants={len(participants['lol'])}; Leaguepedia access is rate-limited; "
        "no retry in this run"
    ), skipped=len(participants["lol"]))
    return {"football_participants": len(participants["football"]), "lol_participants": len(participants["lol"]), "api_football": source, "at": datetime.now(UTC).isoformat()}
