from fastapi import APIRouter, Body, Depends
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models_aposta import ApostaEvent, ApostaMarket, ApostaSelection, ApostaSyncRun
from ..services import aposta_sync, live_source_sync
from ..services.recommender import recommendation_service

router = APIRouter(prefix='/aposta', tags=['aposta'])

MANUAL_MESSAGE = 'Colocar CSV en /opt/pirapire/data/imports/aposta o configurar APOSTA_BROWSER_WORKER_URL.'


def sync_response(result: dict) -> dict:
    run = result['run']
    return {
        'run_id': run.id,
        'status': run.status,
        'message': run.message,
        'sync_mode': settings.aposta_sync_mode,
        'worker_configured': bool(settings.aposta_browser_worker_url.strip()),
        'imported_or_captured_odds': result.get('imported', 0),
        'mapped_markets': result.get('mapped', 0),
        'unmapped_markets': result.get('unmapped', 0),
        'warnings': result.get('warnings', []),
    }


@router.post('/sync')
def sync(payload: dict = Body(default={}), session: Session = Depends(get_session)) -> dict:
    result = aposta_sync.sync(session, force_refresh=bool(payload.get('force_aposta_refresh')))
    if settings.auto_recommend_on_aposta_sync and result['run'].status in ('success', 'partial'):
        recommendation_service.run(session, mode=payload.get('mode') or 'balanced')
    return sync_response(result)


@router.post('/sync-and-recommend')
def sync_and_recommend(payload: dict = Body(default={}), session: Session = Depends(get_session)) -> dict:
    source_sync = None
    if payload.get('sync_sources_if_stale'):
        source_sync = live_source_sync.sync_if_stale(session, force=bool(payload.get('force_source_refresh')))
    sync_result = aposta_sync.sync(session, force_refresh=bool(payload.get('force_aposta_refresh')))
    run = sync_result['run']
    odds = aposta_sync.current_odds(session, include_past=False)
    matched, unmatched = aposta_sync.match_summary(session, odds)
    if run.status == 'manual_required':
        return {
            'status': 'manual_required',
            'aposta_run_id': run.id,
            'recommendation_run_id': None,
            'imported_or_captured_odds': 0,
            'matched_odds': 0,
            'unmatched_odds': 0,
            'singles': 0,
            'combos': 0,
            'message': run.message or MANUAL_MESSAGE,
            'warnings': sync_result.get('warnings', []),
            'source_sync': source_sync,
        }
    rec = recommendation_service.run(
        session,
        mode=payload.get('mode'),
        sport=payload.get('sport'),
        min_probability=payload.get('min_probability'),
        min_odds=payload.get('min_odds'),
        max_odds=payload.get('max_odds'),
        max_legs=payload.get('max_legs'),
        max_suggestions=payload.get('max_suggestions'),
        min_ev=payload.get('min_ev'),
        min_edge=payload.get('min_edge'),
        risk_max=payload.get('risk_max'),
        coverage_min=payload.get('coverage_min'),
        only_positive_ev=payload.get('only_positive_ev'),
        only_matched=payload.get('only_matched') or False,
        include_stale=payload.get('include_stale'),
        include_unmapped=payload.get('include_unmapped') or False,
        max_combo_odds=payload.get('max_combo_odds'),
        league=payload.get('league'),
        min_sample_size=payload.get('min_sample_size'),
    )
    status = 'success' if run.status == 'success' and rec['status'] == 'success' else 'partial'
    message = run.message or 'Aposta.LA actualizado y recomendaciones recalculadas.'
    if rec.get('total_candidates', 0) == 0:
        message = 'No hay cuotas actuales o futuras: lo importado vencido queda solo como estadistica.'
    return {
        'status': status,
        'aposta_run_id': run.id,
        'recommendation_run_id': rec['run_id'],
        'imported_or_captured_odds': sync_result.get('imported', 0),
        'matched_odds': matched,
        'unmatched_odds': unmatched,
        'singles': rec.get('total_recommendations', 0),
        'combos': rec.get('total_combos', 0),
        'message': message,
        'warnings': sync_result.get('warnings', []),
        'source_sync': source_sync,
    }


@router.get('/status')
def status(session: Session = Depends(get_session)) -> dict:
    last = session.exec(select(ApostaSyncRun).order_by(ApostaSyncRun.id.desc())).first()
    batch = aposta_sync.latest_aposta_batch(session)
    return {'worker_configured': bool(settings.aposta_browser_worker_url.strip()), 'sync_enabled': settings.aposta_sync_enabled, 'sync_mode': settings.aposta_sync_mode, 'import_dir': settings.aposta_import_dir, 'host_import_dir': '/opt/pirapire/data/imports/aposta', 'last_run': last, 'latest_batch_id': batch.id if batch else None, 'message': None if batch else MANUAL_MESSAGE}


@router.get('/options')
def options(sport: str | None = None, competition: str | None = None, event: str | None = None, market: str | None = None, include_stale: bool = False, include_past: bool = False, limit: int = 200, session: Session = Depends(get_session)) -> list:
    rows = aposta_sync.current_odds(session, include_stale=include_stale, include_past=include_past)
    out = []
    for odd in rows:
        label = ' vs '.join([p for p in [odd.team_a, odd.team_b] if p])
        if sport and odd.sport != sport:
            continue
        if competition and competition.lower() not in (odd.competition or '').lower():
            continue
        if event and event.lower() not in label.lower():
            continue
        if market and market.lower() not in (odd.market_text or '').lower():
            continue
        out.append({'id': odd.id, 'sport': odd.sport, 'competition': odd.competition, 'event_date': odd.event_date, 'event': label, 'team_a': odd.team_a, 'team_b': odd.team_b, 'market_text': odd.market_text, 'market_code': odd.market_code, 'line': odd.line, 'selection': odd.selection, 'odds_decimal': odd.odds_decimal, 'bookmaker': odd.bookmaker, 'batch_id': odd.batch_id})
        if len(out) >= limit:
            break
    return out


@router.get('/unmapped-markets')
def unmapped_markets(session: Session = Depends(get_session)) -> list:
    rows = aposta_sync.current_odds(session)
    counts = {}
    for odd in rows:
        if odd.market_code:
            continue
        key = (odd.sport, odd.market_text)
        counts[key] = counts.get(key, 0) + 1
    return [{'sport': sport, 'market_text': text, 'count': count} for (sport, text), count in sorted(counts.items())]


@router.get('/sync-runs')
def sync_runs(limit: int = 50, session: Session = Depends(get_session)) -> list:
    return session.exec(select(ApostaSyncRun).order_by(ApostaSyncRun.id.desc()).limit(limit)).all()


@router.get('/events')
def events(limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(select(ApostaEvent).order_by(ApostaEvent.id.desc()).limit(limit)).all()


@router.get('/markets')
def markets(limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(select(ApostaMarket).order_by(ApostaMarket.id.desc()).limit(limit)).all()


@router.get('/selections')
def selections(limit: int = 200, session: Session = Depends(get_session)) -> list:
    return session.exec(select(ApostaSelection).order_by(ApostaSelection.id.desc()).limit(limit)).all()
