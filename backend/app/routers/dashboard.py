from fastapi import APIRouter, Body, Depends
from sqlmodel import Session, select

from ..database import get_session
from ..services.dashboard_refresh import run_refresh
from ..services.dashboard_state import get_full_state

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/state")
def dashboard_state(session: Session = Depends(get_session)) -> dict:
    return get_full_state(session)


@router.get("/backtest")
def dashboard_backtest(session: Session = Depends(get_session)):
    from ..services.backtesting import backtest_1x2, backtest_over_under

    return {
        "1x2": backtest_1x2(session),
        "over_under_2.5": backtest_over_under(session, line=2.5),
    }


@router.get("/calendar")
def dashboard_calendar(session: Session = Depends(get_session), days: int = 7):
    from ..models_imports import ImportedOdds
    from ..utils.datetime_utils import event_time_display

    rows = session.exec(
        select(ImportedOdds)
        .where(ImportedOdds.source_name == "aposta_la", ImportedOdds.is_current)
        .order_by(ImportedOdds.event_date_sort)
    ).all()

    events = {}
    for row in rows:
        key = (
            row.team_a
            + "|"
            + (row.team_b or "")
            + "|"
            + (row.competition or "")
            + "|"
            + (row.event_date_sort or "")
        )
        if key not in events:
            events[key] = {
                "team_a": row.team_a,
                "team_b": row.team_b,
                "competition": row.competition,
                "event_date": row.event_date_sort,
                "event_date_display": event_time_display(
                    row.event_date_sort, row.event_time_status
                ),
                "event_time_status": row.event_time_status,
                "sport": row.sport,
                "markets": 0,
                "event_id": row.id,
            }
        events[key]["markets"] += 1

    result = sorted(events.values(), key=lambda e: e.get("event_date") or "")
    return result[:50]


@router.post("/refresh")
def dashboard_refresh(
    payload: dict = Body(default={}), session: Session = Depends(get_session)
) -> dict:
    return run_refresh(
        session,
        mode=payload.get("mode", "balanced"),
        sport=payload.get("sport"),
        min_probability=payload.get("min_probability"),
        min_ev=payload.get("min_ev"),
        min_edge=payload.get("min_edge"),
        min_odds=payload.get("min_odds"),
        max_odds=payload.get("max_odds"),
        max_legs=payload.get("max_legs"),
        max_suggestions=payload.get("max_suggestions", 20),
        risk_max=payload.get("risk_max"),
        coverage_min=payload.get("coverage_min"),
        sync_sports_if_stale=payload.get("sync_sports_if_stale", True),
        refresh_aposta=payload.get("refresh_aposta", True),
        use_latest_snapshot_if_no_new_source=payload.get(
            "use_latest_snapshot_if_no_new_source", True
        ),
        league=payload.get("league"),
        min_sample_size=payload.get("min_sample_size"),
    )
