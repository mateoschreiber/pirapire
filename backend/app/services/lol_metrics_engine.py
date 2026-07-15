"""Traceable, series-based LoL statistics."""
import json
from datetime import datetime

from sqlalchemy import or_
from sqlmodel import Session, select

from ..models_lol import (
    LolGameHistory,
    LolMatchEvent,
    LolPlayerGameStat,
    LolSeries,
    LolTeamGameStat,
)
from .lol_team_aliases import canonical_team


def _resolve(session: Session, name: str) -> str:
    return canonical_team(session, name) or name


def _metric(numerator, denominator, valid, total, reason=None):
    if denominator is None or denominator <= 0:
        return {
            "value": None,
            "status": "unavailable",
            "valid_maps": valid,
            "total_maps": total,
            "reason": reason or "insufficient_denominator",
        }
    return {
        "value": round(100 * numerator / denominator, 1),
        "status": "complete" if valid == total else "partial",
        "valid_maps": valid,
        "total_maps": total,
        "reason": None,
    }


def _recent_series(session: Session, team: str, before: datetime):
    # Only Oracle series have map-level statistics. Mixing schedule-only series
    # made valid data look partial and duplicated the same real-world series.
    return session.exec(
        select(LolSeries).where(
            or_(LolSeries.team_a == team, LolSeries.team_b == team),
            LolSeries.source_name == "oracles_elixir",
            LolSeries.complete == True,  # noqa: E712
            LolSeries.last_game_at < before.isoformat(),
        ).order_by(LolSeries.last_game_at.desc()).limit(5)
    ).all()


def _series_games(session: Session, series):
    if getattr(series, "id", None):
        linked = session.exec(select(LolGameHistory).where(LolGameHistory.series_id == series.id)).all()
        if linked:
            return linked
    try:
        ids = json.loads(series.game_ids_json or "[]")
    except json.JSONDecodeError:
        ids = []
    return session.exec(select(LolGameHistory).where(LolGameHistory.id.in_(ids))).all() if ids else []


def _team_payload(session: Session, team_name: str, before: datetime):
    team = _resolve(session, team_name)
    series = _recent_series(session, team, before)
    games = [game for item in series for game in _series_games(session, item)]
    team_rows, opponents = [], []
    series_map_results = {}
    for game in games:
        rows = session.exec(select(LolTeamGameStat).where(LolTeamGameStat.game_id == game.id)).all()
        own = next((row for row in rows if _resolve(session, row.team_name) == team), None)
        if not own:
            continue
        opponent = next((row for row in rows if row.id != own.id), None)
        if not opponent:
            continue
        team_rows.append(own)
        opponents.append(opponent)
        if game.series_id is not None:
            result = series_map_results.setdefault(game.series_id, {"wins": 0, "losses": 0})
            if own.result == 1:
                result["wins"] += 1
            elif own.result == 0:
                result["losses"] += 1

    total = len(games)
    valid = len(team_rows)
    reason = "no_complete_series" if not series else "unresolved_team" if not valid else None

    def percent(field):
        pairs = [(getattr(own, field), getattr(opp, field)) for own, opp in zip(team_rows, opponents)]
        usable = [(own, opp) for own, opp in pairs if own is not None and opp is not None]
        return _metric(sum(own for own, _ in usable), sum(own + opp for own, opp in usable), len(usable), total, reason)

    def absolute(field):
        values = [getattr(row, field) for row in team_rows if getattr(row, field) is not None]
        return {
            "total": sum(values) if values else None,
            "per_map": round(sum(values) / len(values), 2) if values else None,
            "status": "complete" if len(values) == total and total else "partial" if values else "unavailable",
            "valid_maps": len(values),
            "total_maps": total,
            "reason": None if values else (reason or "metric_not_provided"),
        }

    def average(field):
        values = [getattr(row, field) for row in team_rows if getattr(row, field) is not None]
        return {
            "value": round(sum(values) / len(values), 2) if values else None,
            "status": "complete" if len(values) == total and total else "partial" if values else "unavailable",
            "valid_maps": len(values),
            "total_maps": total,
            "reason": None if values else (reason or "metric_not_provided"),
        }

    durations = [row.game_length_seconds for row in team_rows if row.game_length_seconds is not None]
    map_duration = {
        "value": round(sum(durations) / len(durations)) if durations else None,
        "status": "complete" if len(durations) == total and total else "partial" if durations else "unavailable",
        "valid_maps": len(durations),
        "total_maps": total,
        "reason": None if durations else (reason or "metric_not_provided"),
    }
    series_durations = []
    series_wins = 0
    series_losses = 0
    for item in series:
        value = sum(game.game_length_seconds or 0 for game in _series_games(session, item))
        if value:
            series_durations.append(value)
        result = series_map_results.get(item.id, {"wins": 0, "losses": 0})
        if result["wins"] != result["losses"]:
            if result["wins"] > result["losses"]:
                series_wins += 1
            else:
                series_losses += 1
    decided_series = series_wins + series_losses

    payload = {
        "team_name": team,
        "series_used": len(series),
        "series_wins": series_wins,
        "series_losses": series_losses,
        "win_rate_pct": round(100 * series_wins / decided_series, 1) if decided_series else None,
        "maps_used": valid,
        "series": [
            {
                "id": item.id,
                "date": item.last_game_at,
                "opponent": item.team_b if item.team_a == team else item.team_a,
                "score": f"{item.score_a}-{item.score_b}",
                "maps": item.maps_count,
                "source": item.source_name,
            }
            for item in series
        ],
        "metrics": {
            key: percent(key)
            for key in ("towers", "inhibitors", "kills", "deaths", "dragons", "barons", "gold")
        },
        "averages": {
            key: average(key)
            for key in ("towers", "inhibitors", "kills", "deaths", "dragons", "barons", "gold")
        },
        "objective_totals": {
            "dragons": absolute("dragons"),
            "barons": absolute("barons"),
        },
        "avg_map_duration_seconds": map_duration,
        "avg_series_duration_seconds": {
            "value": round(sum(series_durations) / len(series_durations)) if series_durations else None,
            "status": "complete" if series_durations else "unavailable",
            "valid_maps": valid,
            "total_maps": total,
            "reason": None if series_durations else reason,
        },
    }
    payload["metrics"]["final_gold"] = payload["metrics"].pop("gold")
    statuses = [metric["status"] for metric in payload["averages"].values()]
    payload["coverage"] = (
        "complete" if statuses and all(status == "complete" for status in statuses)
        else "partial" if any(status != "unavailable" for status in statuses)
        else "unavailable"
    )
    payload["reason"] = reason
    return payload, games, team_rows


def _players(session: Session, team: str, games, team_rows):
    ids = [game.id for game in games]
    rows = session.exec(select(LolPlayerGameStat).where(LolPlayerGameStat.game_id.in_(ids))).all() if ids else []
    rows = [row for row in rows if row.team_name and _resolve(session, row.team_name) == team]
    denominators = {
        "kills": sum(row.kills or 0 for row in team_rows),
        "deaths": sum(row.deaths or 0 for row in team_rows),
        "gold": sum(row.gold or 0 for row in team_rows),
    }
    grouped = {}
    for row in rows:
        if not row.player_name:
            continue
        item = grouped.setdefault(row.player_name, {
            "player_name": row.player_name,
            "role": row.role,
            "games": set(),
            "kills": 0,
            "deaths": 0,
            "gold": 0,
            "cs": 0,
            "cs_valid_maps": 0,
        })
        item["games"].add(row.game_id)
        for key in ("kills", "deaths", "gold"):
            item[key] += getattr(row, key) or 0
        if row.cs is not None:
            item["cs"] += row.cs
            item["cs_valid_maps"] += 1

    role_order = {"top": 0, "jng": 1, "jungle": 1, "jg": 1, "mid": 2, "bot": 3, "adc": 3, "sup": 4, "support": 4}
    role_label = {"top": "Top", "jng": "Jg", "jungle": "Jg", "jg": "Jg", "mid": "Mid", "bot": "ADC", "adc": "ADC", "sup": "Supp", "support": "Supp"}
    output = []
    for item in grouped.values():
        def pct(key, denominator):
            return round(100 * item[key] / denominator, 1) if denominator else None

        maps = len(item["games"])
        role_key = (item["role"] or "").strip().lower()
        output.append({
            "player_name": item["player_name"],
            "role": role_label.get(role_key, item["role"]),
            "role_order": role_order.get(role_key, 99),
            "maps_played": maps,
            "kills": item["kills"],
            "kills_pct": pct("kills", denominators["kills"]),
            "deaths": item["deaths"],
            "deaths_pct": pct("deaths", denominators["deaths"]),
            "gold_per_map": round(item["gold"] / maps, 1) if maps else None,
            "cs_per_map": round(item["cs"] / item["cs_valid_maps"], 1) if item["cs_valid_maps"] else None,
            "cs_status": "available" if item["cs_valid_maps"] else "unavailable",
        })
    output.sort(key=lambda item: (item["role_order"], item["player_name"].lower()))
    for item in output:
        item.pop("role_order", None)
    return output


def _estimated_market(team_a: dict, team_b: dict, team_a_name: str, team_b_name: str) -> dict:
    sample_a = team_a["series_wins"] + team_a["series_losses"]
    sample_b = team_b["series_wins"] + team_b["series_losses"]
    if not sample_a or not sample_b:
        return {
            "available": False,
            "model": "Forma de las últimas 5 series",
            "reason": "Se requiere al menos una serie decidida por equipo.",
        }
    # Laplace smoothing avoids impossible 0%/100% probabilities in a five-series sample.
    strength_a = (team_a["series_wins"] + 1) / (sample_a + 2)
    strength_b = (team_b["series_wins"] + 1) / (sample_b + 2)
    probability_a = strength_a / (strength_a + strength_b)
    probability_b = 1 - probability_a
    return {
        "available": True,
        "model": "Forma de las últimas 5 series",
        "method": "Probabilidad relativa con suavizado Laplace",
        "team_a": {
            "name": team_a_name,
            "probability_pct": round(probability_a * 100, 1),
            "decimal_odds": round(1 / probability_a, 2),
            "series_wins": team_a["series_wins"],
            "series_used": sample_a,
        },
        "team_b": {
            "name": team_b_name,
            "probability_pct": round(probability_b * 100, 1),
            "decimal_odds": round(1 / probability_b, 2),
            "series_wins": team_b["series_wins"],
            "series_used": sample_b,
        },
    }


def compute_match_statistics(session: Session, match_key: str):
    match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    if not match:
        return None
    team_a, games_a, rows_a = _team_payload(session, match.team_a, match.start_time_utc)
    team_b, games_b, rows_b = _team_payload(session, match.team_b, match.start_time_utc)
    return {
        "team_a": team_a,
        "team_b": team_b,
        "team_a_name": match.team_a,
        "team_b_name": match.team_b,
        "players_a": _players(session, team_a["team_name"], games_a, rows_a),
        "players_b": _players(session, team_b["team_name"], games_b, rows_b),
        "estimated_market": _estimated_market(team_a, team_b, match.team_a, match.team_b),
        "data_notes": {
            "odds": "Las cuotas calculadas son una estimación estadística interna y no representan una casa de apuestas.",
            "sample": "Estadísticas calculadas sobre las últimas 5 series con mapas disponibles.",
        },
    }, {"team_a": team_a["coverage"], "team_b": team_b["coverage"]}


def precompute_upcoming_stats(session: Session):
    return {"precomputed": 0, "total_scheduled": 0}
