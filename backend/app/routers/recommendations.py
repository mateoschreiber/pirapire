import json

from fastapi import APIRouter, Body, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..models_recommendations import BetRecommendation, ComboRecommendation, ComboRecommendationLeg, RecommendationRun
from ..services import history_service, live_source_sync
from ..services.recommender import recommendation_service

router = APIRouter(prefix='/recommendations', tags=['recommendations'])


@router.post('/run')
def run_recommendations(payload: dict = Body(default={}), session: Session = Depends(get_session)) -> dict:
    source_sync = None
    if payload.get('sync_sources_if_stale'):
        source_sync = live_source_sync.sync_if_stale(session, force=bool(payload.get('force_source_refresh')))
    result = recommendation_service.run(
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
    result['source_sync'] = source_sync
    return result


def latest_run_id(session: Session, mode: str | None) -> int | None:
    query = select(RecommendationRun).order_by(RecommendationRun.id.desc())
    if mode:
        query = query.where(RecommendationRun.mode == mode)
    run = session.exec(query).first()
    return run.id if run else None


def _latest_run_id(session: Session, mode: str | None) -> int | None:
    return latest_run_id(session, mode)


def bet_payload(row: BetRecommendation) -> dict:
    data = row.model_dump()
    ctx = {}
    if row.source_context_json:
        try:
            ctx = json.loads(row.source_context_json)
        except Exception:
            ctx = {}
    data['edge'] = ctx.get('edge')
    data['league'] = ctx.get('league')
    data['model_confidence'] = ctx.get('model_confidence')
    data['sample_size'] = ctx.get('sample_size')
    data['match_confidence'] = ctx.get('match_confidence')
    data['matched_source'] = ctx.get('matched_source')
    data['matched_event_id'] = ctx.get('matched_event_id')
    data['match_reason'] = ctx.get('match_reason')
    data['explanation'] = ctx.get('explanation')
    return data


@router.get('/bets')
def list_bets(run_id: int | None = None, mode: str | None = None, sport: str | None = None, limit: int = 50, session: Session = Depends(get_session)) -> list:
    if run_id is None:
        run_id = latest_run_id(session, mode)
    if run_id is None:
        return []
    query = select(BetRecommendation).where(BetRecommendation.run_id == run_id)
    if sport:
        query = query.where(BetRecommendation.sport == sport)
    query = query.order_by(BetRecommendation.rank_score.desc()).limit(limit)
    return [bet_payload(row) for row in session.exec(query).all()]


@router.get('/combos')
def list_combos(run_id: int | None = None, mode: str | None = None, limit: int = 50, session: Session = Depends(get_session)) -> list:
    if run_id is None:
        run_id = latest_run_id(session, mode)
    if run_id is None:
        return []
    combos = session.exec(select(ComboRecommendation).where(ComboRecommendation.run_id == run_id).order_by(ComboRecommendation.rank_score.desc()).limit(limit)).all()
    result = []
    for combo in combos:
        legs = session.exec(select(ComboRecommendationLeg).where(ComboRecommendationLeg.combo_id == combo.id).order_by(ComboRecommendationLeg.leg_order)).all()
        result.append({'combo': combo, 'legs': legs})
    return result


@router.get('/latest')
def latest(mode: str | None = None, sport: str | None = None, limit: int = 20, session: Session = Depends(get_session)) -> dict:
    run_id = latest_run_id(session, mode)
    if run_id is None:
        return {'run': None, 'bets': [], 'combos': []}
    run = session.get(RecommendationRun, run_id)
    return {'run': run, 'bets': list_bets(run_id=run_id, mode=None, sport=sport, limit=limit, session=session), 'combos': list_combos(run_id=run_id, mode=None, limit=limit, session=session)}


@router.post('/{recommendation_id}/save-to-history')
def save_bet_to_history(recommendation_id: int, session: Session = Depends(get_session)) -> dict:
    rec = session.get(BetRecommendation, recommendation_id)
    if rec is None:
        raise HTTPException(status_code=404, detail='recommendation not found')
    payload = {'sport': rec.sport, 'match_label': rec.event_label, 'market_code': rec.market_code, 'market_text': rec.market_text, 'line': rec.line, 'selection': rec.selection_text}
    analysis = {'odds_decimal': rec.odds_decimal, 'implied_probability': rec.implied_probability, 'model_probability': rec.model_probability, 'fair_odds': rec.fair_odds, 'expected_value': rec.expected_value, 'risk_label': rec.risk_label}
    saved = history_service.save_prediction(session, payload, analysis)
    return {'status': 'ok', 'prediction_id': saved.id}


@router.post('/combos/{combo_id}/save-to-history')
def save_combo_to_history(combo_id: int, session: Session = Depends(get_session)) -> dict:
    combo = session.get(ComboRecommendation, combo_id)
    if combo is None:
        raise HTTPException(status_code=404, detail='combo not found')
    legs_rows = session.exec(select(ComboRecommendationLeg).where(ComboRecommendationLeg.combo_id == combo_id).order_by(ComboRecommendationLeg.leg_order)).all()
    analysis = {'combo_probability': combo.model_probability, 'combo_fair_odds': combo.fair_odds, 'offered_odds': combo.offered_odds, 'expected_value': combo.expected_value, 'risk_label': combo.risk_label}
    legs = [{'market_code': leg.market_code, 'market_text': leg.market_text, 'line': leg.line, 'selection': leg.selection_text, 'odds_decimal': leg.odds_decimal, 'probability': leg.model_probability} for leg in legs_rows]
    saved = history_service.save_combo(session, combo.name, combo.sport, analysis, legs)
    return {'status': 'ok', 'combo_id': saved.id}
