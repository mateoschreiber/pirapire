"""LoL probability features (v1) from imported Oracle's Elixir data."""

from collections import defaultdict

from sqlmodel import Session, select

from ...models_imports import LolOracleGame

ESTIMATED_ONLY = {
    "player_kills_over_under",
    "player_deaths_over_under",
    "role_kills_over_under",
}


def _game_total_kills(session: Session) -> list[int]:
    rows = session.exec(select(LolOracleGame)).all()
    per_game = defaultdict(int)
    seen = defaultdict(int)
    for row in rows:
        if row.team_kills is not None:
            per_game[row.source_game_id] += row.team_kills
            seen[row.source_game_id] += 1
    # only games with both team rows give a meaningful total
    return [total for gid, total in per_game.items() if seen[gid] >= 2]


def estimate(session: Session, market_code: str, odds_decimal: float, context: dict):
    """Return (model_probability|None, coverage_status)."""
    context = context or {}
    if market_code == "total_kills_over_under":
        line = context.get("line")
        if line is None:
            return None, None
        totals = _game_total_kills(session)
        if len(totals) >= 3:
            over = sum(1 for t in totals if t > line)
            prob = over / len(totals)
            selection = (context.get("selection") or "over").lower()
            if selection == "under":
                prob = 1.0 - prob
            prob = min(0.95, max(0.05, prob))
            return prob, "heuristic"
        return None, None

    if market_code in ESTIMATED_ONLY:
        return None, "estimated_only"

    return None, None
