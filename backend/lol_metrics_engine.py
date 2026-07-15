from datetime import datetime, timezone
from sqlmodel import Session, select
from ..models_lol import (
    LolMatchEvent, LolGameHistory, LolTeamGameStat, LolPlayerGameStat,
    LolMatchStatisticsReadModel, LolTeamAlias, LolSeries,
)

def _now():
    return datetime.now(timezone.utc)

def _resolve_team(session: Session, team_name: str):
    alias = session.exec(select(LolTeamAlias).where(LolTeamAlias.alias == team_name)).first()
    return alias.canonical_team if alias else team_name

def _get_recent_series_game_ids(session: Session, team_name: str, before_utc: datetime, limit: int = 10):
    team = _resolve_team(session, team_name)
    for name in (team, team_name):
        series = session.exec(
            select(LolSeries)
            .where(LolSeries.team_a == name)
            .where(LolSeries.last_game_at < before_utc.isoformat())
            .where(LolSeries.complete == True)  # noqa: E712
            .order_by(LolSeries.last_game_at.desc())
            .limit(limit)
        ).all()
        if series:
            break
        series = session.exec(
            select(LolSeries)
            .where(LolSeries.team_b == name)
            .where(LolSeries.last_game_at < before_utc.isoformat())
            .where(LolSeries.complete == True)  # noqa: E712
            .order_by(LolSeries.last_game_at.desc())
            .limit(limit)
        ).all()
        if series:
            break
    return list(series) if series else []

def _get_game_ids_from_series(series_list):
    ids = set()
    for s in series_list:
        if s.game_ids_json:
            try: ids.update(json.loads(s.game_ids_json))
            except: pass
    return ids

def _compute_team_stats(session, team_name, match_key):
    match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    if not match:
        return None
    team = _resolve_team(session, team_name)
    series_list = _get_recent_series_game_ids(session, team_name, match.start_time_utc)
    if not series_list:
        return {"team_name": team, "series_used": 0, "maps_used": 0, "coverage": "unavailable",
                "towers_pct": None, "inhibitors_pct": None, "kills_pct": None, "deaths_pct": None,
                "dragons_pct": None, "barons_pct": None, "final_gold_pct": None,
                "avg_map_duration_seconds": None, "avg_series_duration_seconds": None,
                "series_used_list": [], "date_from": None, "date_to": None}

    game_ids = _get_game_ids_from_series(series_list)
    team_rows = session.exec(select(LolTeamGameStat).where(LolTeamGameStat.game_id.in_(game_ids))).all()

    # For each team game, find opponent in same game
    opponent_rows = []
    for tr in team_rows:
        opp = session.exec(select(LolTeamGameStat).where(LolTeamGameStat.game_id == tr.game_id, LolTeamGameStat.id != tr.id)).first()
        if opp:
            opponent_rows.append(opp)

    towers_t = sum((r.towers or 0) for r in team_rows)
    towers_o = sum((r.towers or 0) for r in opponent_rows)
    inhibs_t = sum((r.inhibitors or 0) for r in team_rows)
    inhibs_o = sum((r.inhibitors or 0) for r in opponent_rows)
    kills_t = sum((r.kills or 0) for r in team_rows)
    kills_o = sum((r.kills or 0) for r in opponent_rows)
    deaths_t = sum((r.deaths or 0) for r in team_rows)
    deaths_o = sum((r.deaths or 0) for r in opponent_rows)
    dragons_t = sum((r.dragons or 0) for r in team_rows)
    dragons_o = sum((r.dragons or 0) for r in opponent_rows)
    barons_t = sum((r.barons or 0) for r in team_rows)
    barons_o = sum((r.barons or 0) for r in opponent_rows)
    gold_t = sum((r.gold or 0) for r in team_rows)
    gold_o = sum((r.gold or 0) for r in opponent_rows)

    def pct(t, o):
        d = t + o
        return round(100 * t / d, 1) if d > 0 else None

    durations = [r.game_length_seconds for r in team_rows if r.game_length_seconds]
    avg_map = round(sum(durations) / len(durations)) if durations else None

    series_durations = []
    for s in series_list:
        gids = _get_game_ids_from_series([s])
        g_rows = session.exec(select(LolGameHistory).where(LolGameHistory.id.in_(gids))).all()
        dur = sum((r.game_length_seconds or 0) for r in g_rows)
        if dur > 0:
            series_durations.append(dur)
    avg_series = round(sum(series_durations) / len(series_durations)) if series_durations else None

    has_data = bool(team_rows) and bool(opponent_rows)

    return {
        "team_name": team, "series_used": len(series_list), "maps_used": len(team_rows),
        "coverage": "complete" if has_data and len(team_rows) >= 5 else "partial" if has_data else "unavailable",
        "towers_pct": pct(towers_t, towers_o), "inhibitors_pct": pct(inhibs_t, inhibs_o),
        "kills_pct": pct(kills_t, kills_o), "deaths_pct": pct(deaths_t, deaths_o),
        "dragons_pct": pct(dragons_t, dragons_o), "barons_pct": pct(barons_t, barons_o),
        "final_gold_pct": pct(gold_t, gold_o),
        "avg_map_duration_seconds": avg_map, "avg_series_duration_seconds": avg_series,
        "date_from": series_list[-1].first_game_at if series_list else None,
        "date_to": series_list[0].last_game_at if series_list else None,
    }

def _compute_player_stats(session, team_name, match_key):
    match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    if not match: return []
    team = _resolve_team(session, team_name)
    series_list = _get_recent_series_game_ids(session, team_name, match.start_time_utc)
    if not series_list: return []
    game_ids = _get_game_ids_from_series(series_list)
    if not game_ids: return []

    team_rows = session.exec(select(LolTeamGameStat).where(LolTeamGameStat.game_id.in_(game_ids))).all()
    team_stats_by_game = {r.game_id: r for r in team_rows}
    team_kills_total = sum((r.kills or 0) for r in team_rows if r.team_name == team)
    team_deaths_total = sum((r.deaths or 0) for r in team_rows if r.team_name == team)
    team_gold_total = sum((r.gold or 0) for r in team_rows if r.team_name == team)

    # Only players from this team in these games
    players = session.exec(select(LolPlayerGameStat).where(
        LolPlayerGameStat.game_id.in_(game_ids),
        LolPlayerGameStat.team_name == team
    )).all()

    player_map = {}
    for p in players:
        name = p.player_name
        if not name: continue
        if name not in player_map:
            player_map[name] = {"kills": 0, "deaths": 0, "gold": 0, "cs": 0, "solo_kills": 0, "games": set(), "role": p.role}
        d = player_map[name]
        d["kills"] += (p.kills or 0); d["deaths"] += (p.deaths or 0)
        d["gold"] += (p.gold or 0); d["cs"] += (p.cs or 0)
        d["solo_kills"] += (p.solo_kills or 0)
        if p.game_id: d["games"].add(p.game_id)
        d["role"] = p.role or d["role"]

    team_solo_total = sum(d["solo_kills"] for d in player_map.values())
    team_cs_total = sum(d["cs"] for d in player_map.values())

    result = []
    for name, d in sorted(player_map.items()):
        result.append({
            "player_name": name, "role": d["role"], "maps_played": len(d["games"]),
            "kills_pct": round(100 * d["kills"] / team_kills_total, 1) if team_kills_total > 0 else None,
            "deaths_pct": round(100 * d["deaths"] / team_deaths_total, 1) if team_deaths_total > 0 else None,
            "final_gold_pct": round(100 * d["gold"] / team_gold_total, 1) if team_gold_total > 0 else None,
            "solo_kills_pct": round(100 * d["solo_kills"] / team_solo_total, 1) if team_solo_total > 0 else None,
            "cs_pct": round(100 * d["cs"] / team_cs_total, 1) if team_cs_total > 0 else None,
        })
    return result


import json as _json

def compute_match_statistics(session, match_key):
    match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    if not match: return None

    ta = _compute_team_stats(session, match.team_a, match_key)
    tb = _compute_team_stats(session, match.team_b, match_key)
    pa = _compute_player_stats(session, match.team_a, match_key)
    pb = _compute_player_stats(session, match.team_b, match_key)

    payload = {"team_a": ta, "team_b": tb, "team_a_name": match.team_a, "team_b_name": match.team_b,
               "players_a": pa, "players_b": pb}
    coverage = {"team_a": ta["coverage"] if ta else "unavailable",
                "team_b": tb["coverage"] if tb else "unavailable"}

    import hashlib
    fp = hashlib.sha256(_json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    existing = session.exec(select(LolMatchStatisticsReadModel).where(LolMatchStatisticsReadModel.match_key == match_key)).first()
    if existing:
        existing.payload_json = payload; existing.coverage_json = coverage
        existing.input_fingerprint = fp; existing.status = "computed"; existing.updated_at = _now()
        session.add(existing)
    else:
        session.add(LolMatchStatisticsReadModel(match_key=match_key, input_fingerprint=fp, status="computed",
                                                 payload_json=payload, coverage_json=coverage))
    session.commit()
    return payload, coverage

def precompute_upcoming_stats(session):
    from datetime import timedelta
    now = _now()
    window = now + timedelta(hours=48)
    matches = session.exec(select(LolMatchEvent).where(
        LolMatchEvent.start_time_utc >= now, LolMatchEvent.start_time_utc <= window, LolMatchEvent.status == "scheduled"
    )).all()
    computed = 0
    for m in matches:
        try: compute_match_statistics(session, m.match_key); computed += 1
        except Exception as e: log = __import__("logging").getLogger(__name__); log.exception(f"precompute {m.match_key}: {e}")
    return {"precomputed": computed, "total_scheduled": len(matches)}
