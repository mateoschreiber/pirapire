"""Per-field coverage classification for Phase 4B2. No aggregates computed.

Classifies each field for a team's eligible window as one of:
  complete  - present (non-null) in every eligible row
  partial   - present in some but not all eligible rows
  absent    - present in no eligible row
  stale     - only present in rows marked historical_fallback_stale
"""
from __future__ import annotations

from sqlmodel import Session, func, select

from ..models_football import FootballFixturePlayerStat, FootballFixtureStat
from ..models_lol import LolSeries

TEAM_FIELDS = (
    "goals_for", "goals_against", "ht_goals_for", "ht_goals_against",
    "corners", "shots_total", "shots_on_target", "fouls",
    "yellow_cards", "red_cards", "penalties_scored", "penalties_missed",
)


def _classify(values: list, stale_flags: list[bool]) -> str:
    present = [v is not None for v in values]
    if not present:
        return "absent"
    non_stale_present = [p for p, s in zip(present, stale_flags) if not s]
    if any(present) and not non_stale_present:
        return "stale"
    if all(non_stale_present) and non_stale_present:
        return "complete"
    if any(non_stale_present):
        return "partial"
    return "absent"


def classify_football_team(session: Session, team_name: str) -> dict[str, str]:
    rows = session.exec(
        select(FootballFixtureStat).where(
            FootballFixtureStat.provider == "api_football",
            FootballFixtureStat.eligible_for_last_n == True,  # noqa: E712
            (FootballFixtureStat.team_name == team_name),
        )
    ).all()
    stale = [(r.freshness_class == "historical_fallback_stale") for r in rows]
    out = {}
    for field in TEAM_FIELDS:
        out[field] = _classify([getattr(r, field) for r in rows], stale)
    return out


def can_compute_player_leader(session: Session, team_name: str) -> bool:
    """A per-player leader (e.g. fouls) is only computable when fouls data is
    present for every eligible fixture of the team. Missing fouls -> blocked."""
    rows = session.exec(
        select(FootballFixtureStat.fixture_id).where(
            FootballFixtureStat.provider == "api_football",
            FootballFixtureStat.eligible_for_last_n == True,  # noqa: E712
            FootballFixtureStat.team_name == team_name,
        )
    ).all()
    fixture_ids = {r[0] if isinstance(r, tuple) else r for r in rows}
    if not fixture_ids:
        return False
    for fid in fixture_ids:
        players = session.exec(
            select(FootballFixturePlayerStat).where(
                FootballFixturePlayerStat.provider == "api_football",
                FootballFixturePlayerStat.fixture_id == fid,
            )
        ).all()
        if not players:
            return False
        if not any(p.fouls_committed is not None for p in players):
            return False
    return True


def classify_lol_team(session: Session, team_name: str) -> dict:
    from .lol_team_aliases import normalize_text

    from ..models_lol import LolGameHistory, LolPlayerGameStat, LolTeamGameStat

    norm = normalize_text(team_name)
    series = session.exec(
        select(LolSeries).where(
            LolSeries.eligible_for_last_n == True,  # noqa: E712
        )
    ).all()
    mine = [s for s in series if norm in (normalize_text(s.team1), normalize_text(s.team2))]
    maps = team_map_rows = player_map_rows = 0
    for s in mine:
        maps += session.exec(
            select(func.count()).select_from(LolGameHistory).where(
                LolGameHistory.source_name == "leaguepedia_map",
                LolGameHistory.match_id == s.match_id,
            )
        ).one()
        team_map_rows += session.exec(
            select(func.count()).select_from(LolTeamGameStat).where(
                LolTeamGameStat.source_name == "leaguepedia_map",
                LolTeamGameStat.source_game_id.in_(
                    select(LolGameHistory.source_game_id).where(
                        LolGameHistory.source_name == "leaguepedia_map",
                        LolGameHistory.match_id == s.match_id,
                    )
                ),
            )
        ).one()
        player_map_rows += session.exec(
            select(func.count()).select_from(LolPlayerGameStat).where(
                LolPlayerGameStat.source_name == "leaguepedia_map",
                LolPlayerGameStat.source_game_id.in_(
                    select(LolGameHistory.source_game_id).where(
                        LolGameHistory.source_name == "leaguepedia_map",
                        LolGameHistory.match_id == s.match_id,
                    )
                ),
            )
        ).one()
    return {
        "eligible_series": len(mine),
        "series_class": "complete" if len(mine) >= 5 else ("partial" if mine else "absent"),
        "match_ids": [s.match_id for s in mine],
        "maps": maps,
        "team_map_rows": team_map_rows,
        "player_map_rows": player_map_rows,
    }
