from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from ..database import get_session
from ..models_imports import ImportedOdds
from ..models_aposta import ApostaEvent
from ..utils.datetime_utils import event_time_display
from ..services.no_vig import calculate as calculate_no_vig

router = APIRouter(prefix="/api/events", tags=["events"])


def _can_calculate_no_vig(sport: str, market_code: str | None, selection_count: int) -> bool:
    """Compatibility guard; the statistics UI does not render no-vig values."""
    if sport != "football":
        return False
    required = {"match_winner": 3, "total_goals_over_under": 2}
    return required.get(market_code) == selection_count


def _event_for_key(session: Session, event_key: str) -> ApostaEvent:
    event = session.exec(select(ApostaEvent).where(ApostaEvent.event_key == event_key)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _legacy_key(session: Session, legacy_id: str) -> str:
    rows = session.exec(select(ImportedOdds).where(ImportedOdds.id == int(legacy_id))).all()
    keys = {row.event_key for row in rows if row.event_key}
    if not keys:
        raise HTTPException(status_code=404, detail="Legacy event id not found")
    if len(keys) != 1:
        raise HTTPException(status_code=409, detail="Legacy event id resolves ambiguously")
    return keys.pop()


@router.get("/{event_key}")
def event_detail(event_key: str, session: Session = Depends(get_session)):
    """Get all markets and odds for a specific event."""
    if event_key.isdigit():
        key = _legacy_key(session, event_key)
        return RedirectResponse(url=f"/api/events/{key}", status_code=308)
    canonical_event = _event_for_key(session, event_key)
    ref = session.exec(
        select(ImportedOdds).where(ImportedOdds.is_current, ImportedOdds.event_key == event_key).limit(1)
    ).first()
    if not ref:
        raise HTTPException(status_code=404, detail="Event has no active odds")

    # Find all odds for the same event identity
    odds = session.exec(
        select(ImportedOdds)
        .where(
            ImportedOdds.is_current,
            ImportedOdds.event_key == event_key,
        )
        .order_by(ImportedOdds.market_text, ImportedOdds.line)
    ).all()

    # Build event info
    first = ref
    event = {
        "event_key": event_key,
        "event_id": ref.id,
        "sport": first.sport,
        "team_a": first.team_a,
        "team_b": first.team_b,
        "competition": first.competition,
        "event_date": canonical_event.kickoff_utc or first.kickoff_utc or first.event_date_sort,
        "event_date_display": event_time_display(
            canonical_event.kickoff_utc or first.kickoff_utc or first.event_date_sort, first.event_time_status
        ),
        "event_time_status": first.event_time_status,
        "source": first.source_name,
        "total_odds": len(odds),
        "odds_count": len(odds),
        "market_count": len({o.market_key or o.source_market_id or o.canonical_market_id for o in odds}),
    }

    # Group markets
    markets = {}
    for o in odds:
        key = o.market_key or o.source_market_id or f"fallback:{o.canonical_market_id or o.market_text}|{o.line}|{o.period}|{o.player_name or ''}|{o.participant_name or ''}"
        if key not in markets:
            markets[key] = {
                "market_key": key,
                "market_text": o.raw_market_label or o.market_text,
                "raw_market_label": o.raw_market_label or o.market_text,
                "market_code": o.market_code,
                "line": o.line,
                "period": o.period,
                "map_number": o.map_number,
                "participant_name": o.participant_name,
                "player_name": o.player_name,
                "selections": [],
            }
        markets[key]["selections"].append(
            {
                "outcome_key": o.outcome_key or o.source_outcome_id,
                "selection": o.selection,
                "selection_raw": o.raw_outcome_label or o.selection or "",
                "odds_decimal": o.odds_decimal,
                "implied_probability": round(1.0 / o.odds_decimal, 4)
                if o.odds_decimal
                else 0,
            }
        )

    # No-vig is allowed only for explicitly identified, complete football markets.
    market_list = []
    for mk in markets.values():
        selections = mk["selections"]
        total_implied = sum(s["implied_probability"] for s in selections)
        probabilities, reason = calculate_no_vig(first.sport, mk.get("market_code"), selections)
        for selection, probability in zip(selections, probabilities):
            selection["no_vig_probability"] = probability
            selection["implied_pct"] = round(selection["implied_probability"] * 100, 1)
            selection["no_vig_pct"] = round(probability * 100, 1) if probability is not None else None
        available = reason is None
        mk["overround_pct"] = round((total_implied - 1.0) * 100, 2) if available else None
        mk["no_vig_available"] = available
        mk["no_vig_status"] = "available" if available else reason
        mk["selection_count"] = len(selections)
        mk["has_full_market"] = available
        market_list.append(mk)

    event["markets"] = market_list
    return event


@router.get("/{event_key}/statistics")
def event_statistics(event_key: str, session: Session = Depends(get_session)):
    """Descriptive statistics for an event from local materialized read-models.

    Read-only, no external calls, no predictions/odds. Uses the strict per-event
    windows (football last-10 anchor-excluded; LoL last-5 complete series before
    kickoff). Returns coverage per metric and an ``incomplete`` status when the
    window is not fully populated; never invents values.
    """
    if event_key.isdigit():
        key = _legacy_key(session, event_key)
        return RedirectResponse(url=f"/api/events/{key}/statistics", status_code=308)
    from ..services.descriptive_stats import compute_event

    ref = session.exec(
        select(ImportedOdds).where(ImportedOdds.event_key == event_key).limit(1)
    ).first()
    if ref is None:
        raise HTTPException(status_code=404, detail="Event not found")
    payload = compute_event(session, event_key)
    if payload.get("status") == "not_found":
        raise HTTPException(status_code=404, detail="Event not found")
    return payload
