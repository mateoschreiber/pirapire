RISK_PENALTY = {'low': 0.0, 'medium': 0.34, 'high': 0.67, 'very_high': 1.0}
MODES = ('probability', 'profit', 'odds', 'balanced')


def compute_scores(rec: dict) -> dict:
    prob = rec.get('model_probability') or 0.0
    ev = rec.get('expected_value') or 0.0
    edge = rec.get('edge') or 0.0
    implied = rec.get('implied_probability') or 0.0
    match = rec.get('match_confidence') or 0.0
    confidence = rec.get('model_confidence') or 0.0

    rec['probability_score'] = max(0.0, min(1.0, prob))
    rec['odds_score'] = max(0.0, min(1.0, 1.0 - implied))
    rec['profit_score'] = max(0.0, min(1.0, ev))
    rec['edge_score'] = max(0.0, min(1.0, edge * 5.0))
    rec['confidence_score'] = max(0.0, min(1.0, (match + confidence) / 2.0))
    risk_penalty = RISK_PENALTY.get(rec.get('risk_label'), 0.5)
    rec['balanced_score'] = (
        0.34 * rec['probability_score']
        + 0.28 * rec['profit_score']
        + 0.18 * rec['edge_score']
        + 0.14 * rec['confidence_score']
        + 0.10 * rec['odds_score']
        - 0.14 * risk_penalty
    )
    return rec


def sort_key(mode: str):
    if mode == 'probability':
        return lambda r: (r.get('model_probability', 0.0), r.get('edge', 0.0), -RISK_PENALTY.get(r.get('risk_label'), 0.5))
    if mode == 'profit':
        return lambda r: (r.get('expected_value', 0.0), r.get('edge', 0.0), r.get('model_probability', 0.0))
    if mode == 'odds':
        return lambda r: (r.get('odds_decimal', 0.0), r.get('model_probability', 0.0))
    return lambda r: (r.get('balanced_score', 0.0), r.get('expected_value', 0.0), r.get('edge', 0.0))


def rank_score_for(rec: dict, mode: str) -> float:
    if mode == 'probability':
        return rec.get('model_probability', 0.0)
    if mode == 'profit':
        return rec.get('expected_value', 0.0)
    if mode == 'odds':
        return rec.get('odds_decimal', 0.0)
    return rec.get('balanced_score', 0.0)


def rank(recs: list, mode: str) -> list:
    if mode not in MODES:
        mode = 'probability'
    for rec in recs:
        compute_scores(rec)
        rec['rank_score'] = rank_score_for(rec, mode)
        rec['rank_mode'] = mode
    return sorted(recs, key=sort_key(mode), reverse=True)
