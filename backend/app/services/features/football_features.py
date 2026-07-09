"""Football probability features (v1) from normalized FootballMatch data."""

from sqlmodel import Session, select

from ...models_football import FootballMatch

ESTIMATED_ONLY = {
    "cards_over_under",
    "corners_over_under",
    "shots_on_target_over_under",
    "team_shots_on_target_over_under",
    "player_shots_on_target_over_under",
    "player_cards",
    "anytime_goalscorer",
}


def estimate(session: Session, market_code: str, odds_decimal: float, context: dict):
    """Return (model_probability|None, coverage_status)."""
    context = context or {}
    if market_code == "total_goals_over_under":
        line = context.get("line")
        if line is None:
            return None, None
        matches = session.exec(
            select(FootballMatch).where(FootballMatch.home_score.is_not(None))
        ).all()
        totals = [
            (m.home_score or 0) + (m.away_score or 0)
            for m in matches
            if m.home_score is not None and m.away_score is not None
        ]
        if len(totals) >= 5:
            over = sum(1 for t in totals if t > line)
            prob = over / len(totals)
            selection = (context.get("selection") or "over").lower()
            if selection == "under":
                prob = 1.0 - prob
            # keep away from degenerate 0/1
            prob = min(0.95, max(0.05, prob))
            return prob, "heuristic"
        return None, None

    if market_code in ESTIMATED_ONLY:
        return None, "estimated_only"

    # match_winner, double_chance, both_teams_to_score, team_goals: no model yet.
    return None, None
