"""Canonical event identity and capture graph helpers."""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime

from sqlmodel import Session, select

from ..models_aposta import ApostaEvent, CanonicalMarket, CanonicalOutcome


def canonical_text(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", value).strip().casefold()


def utc_datetime(value: datetime | str | None) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def event_key_for(
    *, source: str, source_event_id: str | None, sport: str | None,
    team_a: str | None, team_b: str | None, competition: str | None,
    kickoff_utc: datetime | str | None,
) -> str:
    """Stable public key: native provider id when present, documented hash otherwise."""
    source = canonical_text(source) or "unknown"
    if source_event_id:
        payload = ["native", source, str(source_event_id).strip()]
    else:
        kickoff = utc_datetime(kickoff_utc)
        if kickoff is None:
            raise ValueError("Cannot create event_key without source_event_id or kickoff_utc")
        payload = [
            "derived", source, canonical_text(sport), canonical_text(team_a),
            canonical_text(team_b), canonical_text(competition),
            kickoff.isoformat(),
        ]
    digest = hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode()).hexdigest()
    return f"evt_{digest[:32]}"


def _event_fingerprint(event: ApostaEvent) -> tuple:
    kickoff = utc_datetime(event.kickoff_utc or event.start_time)
    return (
        canonical_text(event.source), str(event.source_event_id or ""),
        canonical_text(event.sport), canonical_text(event.team_a), canonical_text(event.team_b),
        canonical_text(event.competition), kickoff.isoformat() if kickoff else "",
    )


def upsert_event(session: Session, row: dict, snapshot_id: int) -> ApostaEvent:
    source = canonical_text(row.get("source") or "aposta_la")
    kickoff = utc_datetime(row.get("kickoff_utc") or row.get("event_date"))
    source_event_id = row.get("source_event_id")
    key = event_key_for(
        source=source, source_event_id=source_event_id, sport=row.get("sport"),
        team_a=row.get("team_a"), team_b=row.get("team_b"),
        competition=row.get("competition"), kickoff_utc=kickoff,
    )
    event = session.exec(select(ApostaEvent).where(ApostaEvent.event_key == key)).first()
    if event is not None:
        candidate = ApostaEvent(
            source=source, source_event_id=str(source_event_id) if source_event_id else None,
            sport=row.get("sport"), team_a=row.get("team_a"), team_b=row.get("team_b"),
            competition=row.get("competition"), kickoff_utc=kickoff,
        )
        # A native provider may revise labels; its source id wins. Derived keys
        # must never silently join a distinct event.
        if not source_event_id and _event_fingerprint(event) != _event_fingerprint(candidate):
            raise ValueError(f"event_key collision for {key}")
    else:
        event = ApostaEvent(event_key=key, source=source)
        session.add(event)
    event.source_event_id = str(source_event_id) if source_event_id is not None else None
    event.sport = row.get("sport")
    event.competition = row.get("competition")
    event.team_a = row.get("team_a")
    event.team_b = row.get("team_b")
    event.event_name = " vs ".join(x for x in (event.team_a, event.team_b) if x)
    event.start_time = kickoff
    event.kickoff_utc = kickoff
    event.raw_kickoff_text = row.get("raw_kickoff_text") or row.get("event_date_raw")
    event.external_id = str(source_event_id) if source_event_id is not None else event.external_id
    event.source_url = row.get("source_url")
    event.current_snapshot_id = snapshot_id
    event.status = "active"
    event.expires_at = None
    event.updated_at = datetime.now(UTC)
    session.add(event)
    session.commit()
    session.refresh(event)
    return event


def upsert_market_outcome(session: Session, event: ApostaEvent, row: dict) -> tuple[CanonicalMarket, CanonicalOutcome]:
    market_source_id = str(row.get("source_market_id") or "") or None
    market_payload = [event.event_key, market_source_id, canonical_text(row.get("market_text")), row.get("market_code") or "", row.get("line")]
    market_key = hashlib.sha256(json.dumps(market_payload, separators=(",", ":")).encode()).hexdigest()
    market = session.exec(select(CanonicalMarket).where(CanonicalMarket.identity_key == market_key)).first()
    if market is None:
        market = CanonicalMarket(event_id=event.id, identity_key=market_key, market_text=row["market_text"])
        session.add(market)
    market.source_market_id = market_source_id
    market.market_text = row["market_text"]
    market.market_code = row.get("market_code")
    market.line = row.get("line")
    market.updated_at = datetime.now(UTC)
    session.add(market)
    session.commit()
    session.refresh(market)

    outcome_source_id = str(row.get("source_outcome_id") or "") or None
    outcome_payload = [market.identity_key, outcome_source_id, canonical_text(row.get("selection") or row.get("selection_raw"))]
    outcome_key = hashlib.sha256(json.dumps(outcome_payload, separators=(",", ":")).encode()).hexdigest()
    outcome = session.exec(select(CanonicalOutcome).where(CanonicalOutcome.identity_key == outcome_key)).first()
    if outcome is None:
        outcome = CanonicalOutcome(canonical_market_id=market.id, identity_key=outcome_key, selection_text=row.get("selection") or "")
        session.add(outcome)
    outcome.source_outcome_id = outcome_source_id
    outcome.selection_text = row.get("selection_raw") or row.get("selection") or ""
    outcome.selection_normalized = row.get("selection")
    outcome.updated_at = datetime.now(UTC)
    session.add(outcome)
    session.commit()
    session.refresh(outcome)
    return market, outcome
