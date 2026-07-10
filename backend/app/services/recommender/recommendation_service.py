import json
from datetime import UTC, datetime

from sqlmodel import Session, select

from ...config import settings
from ...models_imports import ImportedOdds
from ...models_recommendations import BetRecommendation, ComboRecommendation, ComboRecommendationLeg, RecommendationRun
from .. import aposta_sync, odds_engine
from ..event_matcher import match_imported_odd
from ..lol_league_catalog import canonical_league
from . import combo_builder, probability_engine, ranking

RISK_ORDER = {'low': 0, 'medium': 1, 'high': 2, 'very_high': 3}
COVERAGE_ORDER = {'model': 4, 'heuristic': 3, 'estimated_only': 2, 'odds_implied_only': 1, 'unsupported': 0}


def event_label(odd) -> str:
    return ' vs '.join([p for p in [odd.team_a, odd.team_b] if p]) or (odd.competition or 'Evento')


def source_context(odd, match: dict, est: dict) -> dict:
    ctx = {
        'source': 'aposta_la',
        'imported_odd_id': odd.id,
        'batch_id': odd.batch_id,
        'competition': odd.competition,
        'league': match.get('league') or canonical_league(odd.competition),
        'event_date': odd.event_date.isoformat() if odd.event_date else None,
        'team_a': odd.team_a,
        'team_b': odd.team_b,
        'edge': est.get('edge'),
        'model_confidence': est.get('model_confidence'),
        'sample_size': est.get('sample_size'),
        'explanation': est.get('explanation'),
    }
    ctx.update(match)
    return ctx


def build_recommendation(session: Session, odd) -> dict:
    match = match_imported_odd(session, odd)
    context = {
        'line': odd.line,
        'selection': odd.selection,
        'team_a': odd.team_a,
        'team_b': odd.team_b,
        'competition': odd.competition,
        'match_confidence': match.get('match_confidence') or 0.0,
        **match,
    }
    est = probability_engine.estimate(session, odd.sport, odd.market_code, odd.odds_decimal, context)
    model_prob = est['model_probability']
    risk = odds_engine.risk_label(model_prob) if 0 < model_prob <= 1 else 'high'
    league = match.get('league') or canonical_league(odd.competition) or odd.competition
    rec = {
        'sport': odd.sport,
        'league': league,
        'event_label': event_label(odd),
        'event_key': '%s:%s:%s:%s' % (odd.sport, odd.team_a, odd.team_b, odd.event_date),
        'market_id': odd.market_id,
        'market_code': odd.market_code,
        'market_text': odd.market_text,
        'selection_text': odd.selection,
        'line': odd.line,
        'odds_decimal': odd.odds_decimal,
        'source': 'aposta_la',
        'model_probability': model_prob,
        'implied_probability': est['implied_probability'],
        'fair_odds': est['fair_odds'],
        'expected_value': est['expected_value'],
        'edge': est['edge'],
        'risk_label': risk,
        'coverage_status': est['coverage_status'],
        'model_confidence': est.get('model_confidence', 0.0),
        'sample_size': est.get('sample_size', 0),
        'match_confidence': match.get('match_confidence') or 0.0,
        'matched_source': match.get('matched_source'),
        'matched_event_id': match.get('matched_event_id'),
        'match_reason': match.get('match_reason'),
        'explanation': est.get('explanation'),
    }
    rec['source_context_json'] = json.dumps(source_context(odd, match, est), default=str)
    return rec


def risk_allowed(label: str | None, risk_max: str | None) -> bool:
    if not risk_max:
        return True
    return RISK_ORDER.get(label or 'high', 2) <= RISK_ORDER.get(risk_max, 3)


def coverage_allowed(label: str | None, coverage_min: str | None) -> bool:
    if not coverage_min:
        return True
    return COVERAGE_ORDER.get(label or 'unsupported', 0) >= COVERAGE_ORDER.get(coverage_min, 0)


def league_matches(odd, league: str | None) -> bool:
    if not league:
        return True
    return canonical_league(odd.competition) == league or (odd.competition or '').upper() == league.upper()


def run(
    session: Session,
    mode: str = None,
    sport: str = None,
    min_probability: float = None,
    min_odds: float = None,
    max_odds: float = None,
    max_legs: int = None,
    max_suggestions: int = None,
    min_ev: float = None,
    min_edge: float = None,
    risk_max: str = None,
    coverage_min: str = None,
    only_positive_ev: bool = None,
    only_matched: bool = False,
    include_stale: bool = None,
    include_unmapped: bool = False,
    max_combo_odds: float = None,
    league: str = None,
    min_sample_size: int = None,
) -> dict:
    mode = mode or settings.recommender_default_mode
    if mode not in ranking.MODES:
        mode = 'probability'
    min_probability = settings.recommender_min_probability if min_probability is None else min_probability
    if min_ev is None and mode in ('profit', 'balanced'):
        min_ev = settings.recommender_min_ev
    if min_edge is None and mode in ('profit', 'balanced'):
        min_edge = settings.recommender_min_edge
    max_legs = settings.recommender_max_combo_legs if max_legs is None else max_legs
    max_suggestions = settings.recommender_max_suggestions if max_suggestions is None else max_suggestions
    include_stale = settings.recommender_include_stale_odds if include_stale is None else include_stale
    if only_positive_ev is None:
        only_positive_ev = mode in ('profit', 'balanced') or settings.recommender_only_positive_ev

    run_row = RecommendationRun(mode=mode, sport=sport, status='running')
    session.add(run_row)
    session.commit()
    session.refresh(run_row)

    odds_rows = aposta_sync.current_odds(session, include_stale=include_stale, include_past=False)
    if not odds_rows:
        manual_rows = session.exec(select(ImportedOdds).order_by(ImportedOdds.id.desc())).all()
        odds_rows = aposta_sync.filter_current_odds(manual_rows)
    recs = []
    for odd in odds_rows:
        if sport and odd.sport != sport:
            continue
        if not league_matches(odd, league):
            continue
        if not odd.odds_decimal or odd.odds_decimal <= 1:
            continue
        if min_odds is not None and odd.odds_decimal < min_odds:
            continue
        if max_odds is not None and odd.odds_decimal > max_odds:
            continue
        if not odd.market_code and not include_unmapped and mode in ('profit', 'balanced'):
            continue
        rec = build_recommendation(session, odd)
        if mode != 'odds' and rec['model_probability'] < min_probability:
            continue
        if min_ev is not None and rec['expected_value'] < min_ev:
            continue
        if min_edge is not None and rec['edge'] < min_edge:
            continue
        if min_sample_size is not None and (rec.get('sample_size') or 0) < min_sample_size:
            continue
        if only_positive_ev and rec['expected_value'] <= 0:
            continue
        if only_matched and rec['match_confidence'] < settings.recommender_min_match_confidence:
            continue
        if not risk_allowed(rec['risk_label'], risk_max):
            continue
        if not coverage_allowed(rec['coverage_status'], coverage_min):
            continue
        if rec.get('coverage_status') == 'unsupported' and odd.sport == 'lol':
            continue
        recs.append(rec)

    ranked = ranking.rank(recs, mode)
    top = ranked[:max_suggestions]

    for rec in top:
        row = BetRecommendation(
            run_id=run_row.id,
            sport=rec.get('sport'),
            event_label=rec.get('event_label'),
            market_id=rec.get('market_id'),
            market_code=rec.get('market_code'),
            market_text=rec.get('market_text'),
            selection_text=rec.get('selection_text'),
            line=rec.get('line'),
            odds_decimal=rec['odds_decimal'],
            implied_probability=rec['implied_probability'],
            model_probability=rec['model_probability'],
            fair_odds=rec['fair_odds'],
            expected_value=rec['expected_value'],
            probability_score=rec.get('probability_score', 0.0),
            profit_score=rec.get('profit_score', 0.0),
            odds_score=rec.get('odds_score', 0.0),
            balanced_score=rec.get('balanced_score', 0.0),
            rank_score=rec.get('rank_score', 0.0),
            rank_mode=mode,
            risk_label=rec.get('risk_label'),
            coverage_status=rec.get('coverage_status'),
            source_context_json=rec.get('source_context_json'),
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        rec['id'] = row.id

    combo_pool = [r for r in top if r.get('match_confidence', 0.0) >= settings.recommender_min_match_confidence or r.get('coverage_status') in ('model', 'heuristic')]
    combos = combo_builder.build(combo_pool, mode, max_legs=max_legs, max_combos=max_suggestions, max_combo_odds=max_combo_odds)
    for combo in combos:
        crow = ComboRecommendation(
            run_id=run_row.id,
            sport=combo.get('sport'),
            name=' + '.join(leg.get('event_label', '') for leg in combo['legs']),
            legs_count=combo['legs_count'],
            offered_odds=combo['offered_odds'],
            model_probability=combo['model_probability'],
            fair_odds=combo['fair_odds'],
            expected_value=combo['expected_value'],
            probability_score=combo.get('probability_score', 0.0),
            profit_score=combo.get('profit_score', 0.0),
            odds_score=combo.get('odds_score', 0.0),
            balanced_score=combo.get('balanced_score', 0.0),
            rank_score=combo.get('rank_score', 0.0),
            rank_mode=mode,
            risk_label=combo.get('risk_label'),
        )
        session.add(crow)
        session.commit()
        session.refresh(crow)
        for order, leg in enumerate(combo['legs'], start=1):
            session.add(ComboRecommendationLeg(
                combo_id=crow.id,
                recommendation_id=leg.get('id'),
                leg_order=order,
                market_code=leg.get('market_code'),
                market_text=leg.get('market_text'),
                selection_text=leg.get('selection_text'),
                line=leg.get('line'),
                odds_decimal=leg.get('odds_decimal'),
                model_probability=leg.get('model_probability', 0.0),
            ))
        session.commit()

    run_row.status = 'success'
    run_row.finished_at = datetime.now(UTC)
    run_row.total_candidates = len(odds_rows)
    run_row.total_recommendations = len(top)
    run_row.message = '%s singles, %s combos (mode=%s)' % (len(top), len(combos), mode)
    if not odds_rows:
        run_row.message += '; no hay cuotas actuales o futuras para recomendar'
    session.add(run_row)
    session.commit()
    session.refresh(run_row)

    return {
        'run_id': run_row.id,
        'mode': mode,
        'status': run_row.status,
        'total_candidates': len(odds_rows),
        'total_recommendations': len(top),
        'total_combos': len(combos),
    }
