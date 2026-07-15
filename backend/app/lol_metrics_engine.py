from datetime import datetime, timezone
from sqlmodel import Session, select, func
from ..models_lol import (
    LolMatchEvent, LolGameHistory, LolTeamGameStat, LolPlayerGameStat,
    LolMatchStatisticsReadModel, LolSeries, LolTeamAlias,
)


def _now():
    return datetime.now(timezone.utc)


def _resolve_team(session: Session, team_name: str):
    alias = session.exec(select(LolTeamAlias).where(LolTeamAlias.alias == team_name)).first()
    return alias.canonical_team if alias else team_name


def _get_last_series(session: Session, team_name: str, before_utc: datetime, limit: int = 10):
    team = _resolve_team(session, team_name)
    stmt = (
        select(LolSeries)
        .where(LolSeries.team_a == team)
        .where(LolSeries.last_game_at < before_utc)
        .order_by(LolSeries.last_game_at.desc())
        .limit(limit)
    )
    series_a = list(session.exec(stmt).all())
    stmt = (
        select(LolSeries)
        .where(LolSeries.team_b == team)
        .where(LolSeries.last_game_at < before_utc)
        .order_by(LolSeries.last_game_at.desc())
        .limit(limit)
    )
    series_b = list(session.exec(stmt).all())
    all_series = sorted(series_a + series_b, key=lambda s: s.last_game_at or "", reverse=True)[:limit]
    return all_series


def _get_game_ids_from_series(series_list):
    ids = set()
    for s in series_list:
        if s.game_ids_json:
            import json
            try:
                ids.update(json.loads(s.game_ids_json))
            except (json.JSONDecodeError, TypeError):
                pass
    return ids


def _compute_team_stats(session: Session, team_name: str, match_key: str):
    match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    if not match:
        return None

    team = _resolve_team(session, team_name)
    opponent = _resolve_team(session, match.team_b if team_name == match.team_a else match.team_a)

    series_list = _get_last_series(session, team, match.start_time_utc)
    opponent_series = _get_last_series(session, opponent, match.start_time_utc)

    game_ids = _get_game_ids_from_series(series_list)
    opp_game_ids = _get_game_ids_from_series(opponent_series)

    if not game_ids:
        return {
            "team_name": team, "series_used": 0, "maps_used": 0,
            "coverage": "unavailable",
            "towers_pct": None, "inhibitors_pct": None, "kills_pct": None,
            "deaths_pct": None, "dragons_pct": None, "barons_pct": None,
            "final_gold_pct": None, "avg_map_duration_seconds": None,
            "avg_series_duration_seconds": None,
        }

    team_rows = session.exec(select(LolTeamGameStat).where(LolTeamGameStat.game_id.in_(game_ids))).all()

    towers_t = sum((r.towers or 0) for r in team_rows)
    inhibs_t = sum((r.inhibitors or 0) for r in team_rows)
    kills_t = sum((r.kills or 0) for r in team_rows)
    deaths_t = sum((r.deaths or 0) for r in team_rows)
    dragons_t = sum((r.dragons or 0) for r in team_rows)
    barons_t = sum((r.barons or 0) for r in team_rows)
    gold_t = sum((r.gold or 0) for r in team_rows)

    opp_rows = session.exec(select(LolTeamGameStat).where(LolTeamGameStat.game_id.in_(opp_game_ids))).all()
    towers_o = sum((r.towers or 0) for r in opp_rows)
    inhibs_o = sum((r.inhibitors or 0) for r in opp_rows)
    kills_o = sum((r.kills or 0) for r in opp_rows)
    deaths_o = sum((r.deaths or 0) for r in opp_rows)
    dragons_o = sum((r.dragons or 0) for r in opp_rows)
    barons_o = sum((r.barons or 0) for r in opp_rows)
    gold_o = sum((r.gold or 0) for r in opp_rows)

    def pct(t, o):
        denom = t + o
        return round(100 * t / denom, 1) if denom > 0 else None

    durations = [r.game_length_seconds for r in team_rows if r.game_length_seconds]
    avg_map = round(sum(durations) / len(durations)) if durations else None

    series_durations = []
    for s in series_list:
        gids = _get_game_ids_from_series([s])
        g_rows = session.exec(select(LolGameHistory).where(LolGameHistory.id.in_(gids))).all()
        dur = sum(r.game_length_seconds or 0 for r in g_rows)
        if dur > 0:
            series_durations.append(dur)
    avg_series = round(sum(series_durations) / len(series_durations)) if series_durations else None

    has_data = bool(durations)
    incomplete = any(r is None for row in team_rows for r in [row.towers, row.inhibitors, row.kills, row.deaths])

    return {
        "team_name": team,
        "series_used": len(series_list),
        "maps_used": len(team_rows),
        "coverage": "complete" if has_data and not incomplete else "partial" if has_data else "unavailable",
        "towers_pct": pct(towers_t, towers_o),
        "inhibitors_pct": pct(inhibs_t, inhibs_o),
        "kills_pct": pct(kills_t, kills_o),
        "deaths_pct": pct(deaths_t, deaths_o),
        "dragons_pct": pct(dragons_t, dragons_o),
        "barons_pct": pct(barons_t, barons_o),
        "final_gold_pct": pct(gold_t, gold_o),
        "avg_map_duration_seconds": avg_map,
        "avg_series_duration_seconds": avg_series,
    }


def _compute_player_stats(session: Session, team_name: str, match_key: str):
    match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    if not match:
        return []

    team = _resolve_team(session, team_name)
    series_list = _get_last_series(session, team, match.start_time_utc)
    game_ids = _get_game_ids_from_series(series_list)
    if not game_ids:
        return []

    team_games = session.exec(select(LolTeamGameStat).where(LolTeamGameStat.game_id.in_(game_ids))).all()
    team_kills_total = sum((r.kills or 0) for r in team_games)
    team_deaths_total = sum((r.deaths or 0) for r in team_games)
    team_gold_total = sum((r.gold or 0) for r in team_games)

    players = session.exec(select(LolPlayerGameStat).where(LolPlayerGameStat.game_id.in_(game_ids))).all()
    player_map = {}
    for p in players:
        name = p.player_name
        if not name:
            continue
        if name not in player_map:
            player_map[name] = {"kills": 0, "deaths": 0, "gold": 0, "cs": 0, "solo_kills": 0, "games": set(), "role": p.role}
        d = player_map[name]
        d["kills"] += (p.kills or 0)
        d["deaths"] += (p.deaths or 0)
        d["gold"] += (p.gold or 0)
        d["cs"] += (p.cs or 0)
        d["solo_kills"] += (p.solo_kills or 0)
        if p.game_id:
            d["games"].add(p.game_id)
        d["role"] = p.role or d["role"]

    team_solo_total = sum(d["solo_kills"] for d in player_map.values())
    team_cs_total = sum(d["cs"] for d in player_map.values())

    result = []
    for name, d in sorted(player_map.items()):
        result.append({
            "player_name": name,
            "role": d["role"],
            "maps_played": len(d["games"]),
            "kills_pct": round(100 * d["kills"] / team_kills_total, 1) if team_kills_total > 0 else None,
            "deaths_pct": round(100 * d["deaths"] / team_deaths_total, 1) if team_deaths_total > 0 else None,
            "final_gold_pct": round(100 * d["gold"] / team_gold_total, 1) if team_gold_total > 0 else None,
            "solo_kills_pct": round(100 * d["solo_kills"] / team_solo_total, 1) if team_solo_total > 0 else None,
            "cs_pct": round(100 * d["cs"] / team_cs_total, 1) if team_cs_total > 0 else None,
        })
    return result


def compute_match_statistics(session: Session, match_key: str):
    match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    if not match:
        return None

    team_a_stats = _compute_team_stats(session, match.team_a, match_key)
    team_b_stats = _compute_team_stats(session, match.team_b, match_key)
    players_a = _compute_player_stats(session, match.team_a, match_key)
    players_b = _compute_player_stats(session, match.team_b, match_key)

    payload = {
        "team_a": team_a_stats,
        "team_b": team_b_stats,
        "team_a_name": match.team_a,
        "team_b_name": match.team_b,
        "players_a": players_a,
        "players_b": players_b,
    }
    coverage = {
        "team_a": team_a_stats["coverage"] if team_a_stats else "unavailable",
        "team_b": team_b_stats["coverage"] if team_b_stats else "unavailable",
    }

    import hashlib, json
    fp = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()

    existing = session.exec(select(LolMatchStatisticsReadModel).where(LolMatchStatisticsReadModel.match_key == match_key)).first()
    if existing:
        existing.payload_json = payload
        existing.coverage_json = coverage
        existing.input_fingerprint = fp
        existing.status = "computed"
        existing.updated_at = _now()
        session.add(existing)
    else:
        model = LolMatchStatisticsReadModel(
            match_key=match_key,
            input_fingerprint=fp,
            status="computed",
            payload_json=payload,
            coverage_json=coverage,
        )
        session.add(model)
    session.commit()

    return payload, coverage


def precompute_upcoming_stats(session: Session):
    now = _now()
    from datetime import timedelta
    window = now + timedelta(hours=48)
    stmt = select(LolMatchEvent).where(
        LolMatchEvent.start_time_utc >= now,
        LolMatchEvent.start_time_utc <= window,
        LolMatchEvent.status == "scheduled",
    )
    matches = session.exec(stmt).all()
    computed = 0
    for m in matches:
        try:
            compute_match_statistics(session, m.match_key)
            computed += 1
        except Exception:
            pass
    return {"precomputed": computed, "total_scheduled": len(matches)}
