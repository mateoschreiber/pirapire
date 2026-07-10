from __future__ import annotations

import json
import threading
from datetime import UTC, datetime

from sqlmodel import Session

from ..config import settings
from . import aposta_sync, live_source_sync
from .aposta_snapshot import current_odds as snapshot_current
from .aposta_snapshot import expired_odds as snapshot_expired
from .dashboard_state import get_full_state
from .event_matcher import match_and_store
from .recommender import recommendation_service

_lock = threading.Lock()
_current_run_id: int | None = None


def now() -> datetime:
    return datetime.now(UTC)


def run_refresh(
    session: Session,
    mode: str = 'balanced',
    sport: str | None = None,
    min_probability: float | None = None,
    min_ev: float | None = None,
    min_edge: float | None = None,
    min_odds: float | None = None,
    max_odds: float | None = None,
    max_legs: int | None = None,
    max_suggestions: int | None = None,
    risk_max: str | None = None,
    coverage_min: str | None = None,
    sync_sports_if_stale: bool = True,
    refresh_aposta: bool = True,
    use_latest_snapshot_if_no_new_source: bool = True,
    league: str | None = None,
    min_sample_size: int | None = None,
) -> dict:
    global _current_run_id

    if not _lock.acquire(blocking=False):
        return {'status': 'running', 'run_id': _current_run_id, 'message': 'Ya hay un refresh en ejecucion'}

    stages = {}
    try:
        t0 = now()

        # Stage 1: Sync sports if stale
        source_sync = None
        if sync_sports_if_stale:
            source_sync = live_source_sync.sync_if_stale(session, force=False)
            stages['sports_sync'] = source_sync

        # Stage 2: Sync Aposta
        aposta_result = None
        if refresh_aposta:
            aposta_result = aposta_sync.sync(session, force_refresh=False)
            stages['aposta_sync'] = {
                'status': aposta_result['run'].status,
                'imported': aposta_result.get('imported', 0),
                'matched_events': aposta_result.get('matched_events', 0),
            }
        elif use_latest_snapshot_if_no_new_source:
            aposta_result = {'run': None, 'imported': 0, 'mapped': 0, 'unmapped': 0}
            stages['aposta_sync'] = {'status': 'skipped', 'message': 'Using latest snapshot'}

        t_after_sync = now()

        # Stage 3: Recalculate recommendations
        rec_result = recommendation_service.run(
            session,
            mode=mode,
            sport=sport,
            min_probability=min_probability,
            min_odds=min_odds,
            max_odds=max_odds,
            max_legs=max_legs,
            max_suggestions=max_suggestions,
            min_ev=min_ev,
            min_edge=min_edge,
            risk_max=risk_max,
            coverage_min=coverage_min,
            league=league,
            min_sample_size=min_sample_size,
        )
        _current_run_id = rec_result.get('run_id')
        stages['recommendations'] = rec_result

        t_final = now()

        # Build response
        state = get_full_state(session)
        stages['timing'] = {
            'sync_stage_seconds': round((t_after_sync - t0).total_seconds(), 2),
            'total_seconds': round((t_final - t0).total_seconds(), 2),
        }

        return {
            'status': 'success' if rec_result.get('status') == 'success' else 'partial',
            'run_id': rec_result.get('run_id'),
            'mode': mode,
            'singles': rec_result.get('total_recommendations', 0),
            'combos': rec_result.get('total_combos', 0),
            'observables': rec_result.get('observables', 0),
            'rejected': rec_result.get('rejected', 0),
            'blockers': state.get('recommendations', {}).get('blockers', []),
            'football': state.get('football', {}),
            'lol': state.get('lol', {}),
            'aposta': state.get('aposta', {}),
            'stages': stages,
            'message': (
                f"{rec_result.get('total_recommendations', 0)} apuestas, "
                f"{rec_result.get('total_combos', 0)} combinadas"
            ),
        }
    except Exception as exc:
        return {
            'status': 'error',
            'run_id': None,
            'message': str(exc),
            'stages': stages,
        }
    finally:
        _lock.release()
