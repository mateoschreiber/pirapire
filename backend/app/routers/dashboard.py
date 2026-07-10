from fastapi import APIRouter, Body, Depends
from sqlmodel import Session

from ..database import get_session
from ..services.dashboard_refresh import run_refresh
from ..services.dashboard_state import get_full_state

router = APIRouter(prefix='/dashboard', tags=['dashboard'])


@router.get('/state')
def dashboard_state(session: Session = Depends(get_session)) -> dict:
    return get_full_state(session)


@router.post('/refresh')
def dashboard_refresh(payload: dict = Body(default={}), session: Session = Depends(get_session)) -> dict:
    return run_refresh(
        session,
        mode=payload.get('mode', 'balanced'),
        sport=payload.get('sport'),
        min_probability=payload.get('min_probability'),
        min_ev=payload.get('min_ev'),
        min_edge=payload.get('min_edge'),
        min_odds=payload.get('min_odds'),
        max_odds=payload.get('max_odds'),
        max_legs=payload.get('max_legs'),
        max_suggestions=payload.get('max_suggestions', 20),
        risk_max=payload.get('risk_max'),
        coverage_min=payload.get('coverage_min'),
        sync_sports_if_stale=payload.get('sync_sports_if_stale', True),
        refresh_aposta=payload.get('refresh_aposta', True),
        use_latest_snapshot_if_no_new_source=payload.get('use_latest_snapshot_if_no_new_source', True),
        league=payload.get('league'),
        min_sample_size=payload.get('min_sample_size'),
    )
