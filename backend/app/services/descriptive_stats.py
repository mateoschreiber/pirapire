"""Phase 4C — descriptive statistics (local, read-only, no predictions).

Materializes descriptive aggregates per Aposta event from already-validated
data:
  * Football: the strict EventTeamHistoryWindow (10 fixtures per team, anchor
    excluded, kickoff_utc < cutoff_utc).
  * LoL: the last 5 *complete* LolSeries before the event kickoff, with their
    Leaguepedia map and player facts.

Rules: null is never turned into zero; every metric carries coverage
(non_null / denominator / required); averages use only the window rows; a
player leader is emitted only when its required coverage is complete; team
deaths in LoL are derived from opponent kills and declared derived=true. No
odds, model or predictive fields are produced here.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import UTC, datetime

from sqlmodel import Session, select

from ..models_football import (
    EventStatisticsReadModel,
    EventTeamHistoryWindow,
    FootballFixturePlayerStat,
    FootballFixtureStat,
)
from ..models_imports import ImportedOdds
from ..models_lol import LolGameHistory, LolPlayerGameStat, LolSeries, LolTeamGameStat

FOOTBALL_WINDOW_N = 10
LOL_SERIES_N = 5
MAP_SOURCE = "leaguepedia_map"

ES_EN_COUNTRY = {
    "suiza": "Switzerland", "noruega": "Norway", "inglaterra": "England",
    "argentina": "Argentina", "brasil": "Brazil", "espana": "Spain",
    "alemania": "Germany", "francia": "France", "italia": "Italy",
    "belgica": "Belgium", "paises bajos": "Netherlands", "holanda": "Netherlands",
    "croacia": "Croatia", "portugal": "Portugal", "uruguay": "Uruguay",
    "estados unidos": "United States", "mexico": "Mexico", "corea del sur": "South Korea",
    "japon": "Japan", "marruecos": "Morocco", "senegal": "Senegal",
}


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _deaccent(value) -> str:
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _english_name(name: str) -> str:
    return ES_EN_COUNTRY.get(_deaccent(name), name)


def _as_utc(dt):
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _mean(values: list, required: int) -> dict:
    """Coverage-aware mean over non-null values. null is never zero."""
    present = [v for v in values if v is not None]
    denom = len(present)
    avg = round(sum(present) / denom, 4) if denom else None
    return {
        "average": avg,
        "values": values,
        "coverage": {"non_null": denom, "denominator": len(values), "required": required},
    }


def _event(session: Session, event_key: str):
    row = session.exec(
        select(ImportedOdds).where(ImportedOdds.event_key == event_key)
    ).first()
    return row


# --------------------------------------------------------------------------
# Football
# --------------------------------------------------------------------------

_FB_FOR_FIELDS = ("goals_for", "goals_against", "corners", "shots_total",
                  "shots_on_target", "fouls", "yellow_cards", "red_cards")


def _fb_window_rows(session, event_key, team) -> list[FootballFixtureStat]:
    windows = session.exec(
        select(EventTeamHistoryWindow)
        .where(EventTeamHistoryWindow.event_key == event_key,
               EventTeamHistoryWindow.team == team)
        .order_by(EventTeamHistoryWindow.rank)
    ).all()
    rows = []
    accepted = {_norm(team), _norm(_english_name(team))}
    for w in windows:
        fx = session.exec(
            select(FootballFixtureStat).where(
                FootballFixtureStat.provider == "fresh_football",
                FootballFixtureStat.source_id == w.fixture_source_id,
                FootballFixtureStat.team_name.in_({team, _english_name(team)}),
            )
        ).first()
        if fx is None:
            # fall back by fixture_id, still restricted to this team
            fx = session.exec(
                select(FootballFixtureStat).where(
                    FootballFixtureStat.provider == "fresh_football",
                    FootballFixtureStat.fixture_id == f"sofa_{w.fixture_source_id}",
                )
            ).first()
        if fx is not None and _norm(fx.team_name) in accepted:
            rows.append((w.rank, fx))
    rows.sort(key=lambda x: x[0])
    return [fx for _, fx in rows]


def _wdl(pairs: list[tuple]) -> dict:
    """pairs of (for, against). Returns W/D/L counts + pct with coverage."""
    present = [(f, a) for f, a in pairs if f is not None and a is not None]
    denom = len(present)
    w = sum(1 for f, a in present if f > a)
    d = sum(1 for f, a in present if f == a)
    lo = sum(1 for f, a in present if f < a)

    def pct(n):
        return round(100.0 * n / denom, 2) if denom else None
    return {
        "win": w, "draw": d, "loss": lo,
        "win_pct": pct(w), "draw_pct": pct(d), "loss_pct": pct(lo),
        "coverage": {"non_null": denom, "denominator": len(pairs), "required": len(pairs)},
    }


def _fb_player_fouls_leader(session, event_key, team, fixture_ids) -> dict:
    """Player with most fouls; only if fouls coverage is complete for the window."""
    required = len(fixture_ids)
    # coverage: every fixture must have at least one player fouls value.
    fixtures_with_fouls = 0
    totals: dict[str, dict] = {}
    for fid in fixture_ids:
        players = session.exec(
            select(FootballFixturePlayerStat).where(
                FootballFixturePlayerStat.provider == "fresh_football",
                FootballFixturePlayerStat.fixture_id == fid,
                FootballFixturePlayerStat.team_name.in_({team, _english_name(team)}),
            )
        ).all()
        has = any(p.fouls_committed is not None for p in players)
        if has:
            fixtures_with_fouls += 1
        for p in players:
            if p.fouls_committed is None:
                continue
            key = p.player_name or p.player_external_id or "?"
            b = totals.setdefault(key, {"player": p.player_name, "total_fouls": 0, "appearances": 0})
            b["total_fouls"] += p.fouls_committed
            b["appearances"] += 1
    complete = required > 0 and fixtures_with_fouls == required
    coverage = {"non_null": fixtures_with_fouls, "denominator": required, "required": required}
    if not complete or not totals:
        return {"leader": None, "status": "incomplete", "coverage": coverage}
    leader = max(totals.values(), key=lambda x: x["total_fouls"])
    leader = dict(leader)
    leader["average_per_appearance"] = round(leader["total_fouls"] / leader["appearances"], 4) if leader["appearances"] else None
    leader["matches"] = leader["appearances"]
    return {"leader": leader, "status": "complete", "coverage": coverage}


def _fb_team_block(session, event_key, team, cutoff) -> dict:
    rows = _fb_window_rows(session, event_key, team)
    fixture_ids = [r.fixture_id for r in rows]
    fixtures = [{
        "rank": i + 1,
        "kickoff_utc": r.kickoff_utc.isoformat() if r.kickoff_utc else None,
        "opponent": r.opponent_name,
        "home": r.is_home,
        "competition": r.competition_name,
        "match_type": r.match_type,
        "goals_for": r.goals_for, "goals_against": r.goals_against,
        "ht_for": r.ht_goals_for, "ht_against": r.ht_goals_against,
        "corners": r.corners, "shots_total": r.shots_total,
        "shots_on_target": r.shots_on_target, "fouls": r.fouls,
        "yellow_cards": r.yellow_cards, "red_cards": r.red_cards,
        "penalties_awarded": r.penalties_awarded,
        "penalties_scored": r.penalties_scored, "penalties_missed": r.penalties_missed,
        "source_id": r.source_id,
    } for i, r in enumerate(rows)]
    n = len(rows)
    metrics = {
        "goals_for": _mean([r.goals_for for r in rows], FOOTBALL_WINDOW_N),
        "goals_against": _mean([r.goals_against for r in rows], FOOTBALL_WINDOW_N),
        "corners_for": _mean([r.corners for r in rows], FOOTBALL_WINDOW_N),
        "shots_for": _mean([r.shots_total for r in rows], FOOTBALL_WINDOW_N),
        "shots_on_target_for": _mean([r.shots_on_target for r in rows], FOOTBALL_WINDOW_N),
        "fouls_committed": _mean([r.fouls for r in rows], FOOTBALL_WINDOW_N),
        "yellow_cards": _mean([r.yellow_cards for r in rows], FOOTBALL_WINDOW_N),
        "red_cards": _mean([r.red_cards for r in rows], FOOTBALL_WINDOW_N),
        # Opponent cards shown as cards received by the opponent (no causal attribution).
        "opponent_yellow_cards_received": _mean([_opp_card(session, r, "yellow") for r in rows], FOOTBALL_WINDOW_N),
        "opponent_red_cards_received": _mean([_opp_card(session, r, "red") for r in rows], FOOTBALL_WINDOW_N),
        "penalties_awarded_for": _mean([r.penalties_awarded for r in rows], FOOTBALL_WINDOW_N),
        "penalties_scored_for": _mean([r.penalties_scored for r in rows], FOOTBALL_WINDOW_N),
        "penalties_missed_for": _mean([r.penalties_missed for r in rows], FOOTBALL_WINDOW_N),
    }
    ht = _wdl([(r.ht_goals_for, r.ht_goals_against) for r in rows])
    ft = _wdl([(r.goals_for, r.goals_against) for r in rows])
    leader = _fb_player_fouls_leader(session, event_key, team, fixture_ids)
    return {
        "team": team,
        "window_size": n,
        "fixtures": fixtures,
        "metrics": metrics,
        "wdl_ht": ht,
        "wdl_ft": ft,
        "fouls_leader": leader,
    }


def _opp_card(session, row: FootballFixtureStat, color: str):
    """The opponent's own cards in that same fixture (received by opponent)."""
    other = session.exec(
        select(FootballFixtureStat).where(
            FootballFixtureStat.provider == row.provider,
            FootballFixtureStat.fixture_id == row.fixture_id,
            FootballFixtureStat.team_side != row.team_side,
        )
    ).first()
    if other is None:
        return None
    return other.yellow_cards if color == "yellow" else other.red_cards


def _football_statistics(session, event_key, event) -> dict:
    cutoff = _as_utc(event.kickoff_utc)
    teams = [t for t in (event.team_a, event.team_b) if t]
    blocks = {t: _fb_team_block(session, event_key, t, cutoff) for t in teams}
    complete = all(b["window_size"] == FOOTBALL_WINDOW_N for b in blocks.values()) and len(blocks) == 2
    return {
        "sport": "football",
        "event_key": event_key,
        "teams": [event.team_a, event.team_b],
        "cutoff_utc": cutoff.isoformat() if cutoff else None,
        "window": "EventTeamHistoryWindow(last-10, anchor excluded)",
        "status": "complete" if complete else "incomplete",
        "team_stats": blocks,
    }


# --------------------------------------------------------------------------
# LoL
# --------------------------------------------------------------------------

def _parse_series_dt(value):
    return _as_utc(_try_dt(str(value or "").replace(" ", "T")))


def _try_dt(text):
    try:
        return datetime.fromisoformat(text[:25])
    except (ValueError, TypeError):
        return None


def _lol_series_window(session, team, other, cutoff) -> list[LolSeries]:
    """Last LOL_SERIES_N complete series for a team, before cutoff, excluding
    the anchor series (head-to-head vs the other participant near cutoff)."""
    rows = session.exec(
        select(LolSeries).where(LolSeries.series_status == "complete")
    ).all()
    tset = {_norm(team)}
    oset = {_norm(other)} if other else set()
    mine = []
    for s in rows:
        names = {_norm(s.team1), _norm(s.team2)}
        if not (tset & names):
            continue
        d = _parse_series_dt(s.date)
        if cutoff is not None and d is not None and d >= cutoff:
            continue
        # exclude anchor head-to-head near cutoff
        if oset and (oset & names) and d is not None and cutoff is not None and abs((cutoff - d).total_seconds()) <= 2 * 86400:
            continue
        mine.append((d, s))
    mine.sort(key=lambda x: (x[0] is not None, x[0] or datetime.min.replace(tzinfo=UTC)), reverse=True)
    return [s for _, s in mine[:LOL_SERIES_N]]


def _series_maps(session, match_id) -> list[LolGameHistory]:
    return session.exec(
        select(LolGameHistory).where(
            LolGameHistory.source_name == MAP_SOURCE,
            LolGameHistory.match_id == match_id,
        )
    ).all()


def _team_map_stat(session, gid, team):
    return session.exec(
        select(LolTeamGameStat).where(
            LolTeamGameStat.source_name == MAP_SOURCE,
            LolTeamGameStat.source_game_id == gid,
            LolTeamGameStat.team_name == team,
        )
    ).first()


def _lol_team_block(session, team, other, cutoff) -> dict:
    series = _lol_series_window(session, team, other, cutoff)
    series_list = []
    # per-map accumulators
    kills, deaths, towers, inhibs = [], [], [], []
    total_map_kills = []
    win_durations, loss_durations, all_durations = [], [], []
    player_kills: dict[str, dict] = {}
    player_deaths: dict[str, dict] = {}
    maps_count = 0
    for s in series:
        maps = _series_maps(session, s.match_id)
        # team result in series
        s_dur = 0
        s_dur_present = False
        wins = 0
        for g in maps:
            # Identify this team's canonical name as stored on the map.
            cand = None
            for nm in (g.blue_team, g.red_team):
                if _norm(nm) == _norm(team):
                    cand = nm
                    break
            if cand is None:
                continue
            opp_name = g.red_team if _norm(cand) == _norm(g.blue_team) else g.blue_team
            tstat = _team_map_stat(session, g.source_game_id, cand)
            ostat = _team_map_stat(session, g.source_game_id, opp_name)
            maps_count += 1
            if tstat:
                kills.append(tstat.team_kills)
                deaths.append(tstat.team_deaths)
                towers.append(tstat.towers)
                inhibs.append(tstat.inhibitors)
                tk = tstat.team_kills
                ok = ostat.team_kills if ostat else None
                total_map_kills.append((tk + ok) if (tk is not None and ok is not None) else None)
                if g.game_length_seconds is not None:
                    all_durations.append(g.game_length_seconds)
                    if tstat.result == 1:
                        win_durations.append(g.game_length_seconds)
                    elif tstat.result == 0:
                        loss_durations.append(g.game_length_seconds)
                if tstat.result == 1:
                    wins += 1
            if g.game_length_seconds is not None:
                s_dur += g.game_length_seconds
                s_dur_present = True
            # players of this team on this map
            pls = session.exec(
                select(LolPlayerGameStat).where(
                    LolPlayerGameStat.source_name == MAP_SOURCE,
                    LolPlayerGameStat.source_game_id == g.source_game_id,
                    LolPlayerGameStat.team_name == cand,
                )
            ).all()
            for p in pls:
                pk = player_kills.setdefault(p.player_name or "?", {"player": p.player_name, "kills": 0, "maps": 0})
                if p.kills is not None:
                    pk["kills"] += p.kills
                    pk["maps"] += 1
                pd = player_deaths.setdefault(p.player_name or "?", {"player": p.player_name, "deaths": 0, "maps": 0})
                if p.deaths is not None:
                    pd["deaths"] += p.deaths
                    pd["maps"] += 1
        opp = s.team2 if _norm(s.team1) == _norm(team) else s.team1
        series_list.append({
            "match_id": s.match_id,
            "date": s.date,
            "opponent": opp,
            "tournament": s.tournament,
            "maps": len(maps),
            "maps_won_by_team": wins,
            "series_duration_seconds": s_dur if s_dur_present else None,
        })

    def _avg(vals):
        pres = [v for v in vals if v is not None]
        return round(sum(pres) / len(pres), 4) if pres else None

    player_kill_avg = [
        {"player": v["player"], "total_kills": v["kills"], "maps": v["maps"],
         "kills_per_map": round(v["kills"] / v["maps"], 4) if v["maps"] else None}
        for v in player_kills.values()
    ]
    player_death_avg = [
        {"player": v["player"], "total_deaths": v["deaths"], "maps": v["maps"],
         "deaths_per_map": round(v["deaths"] / v["maps"], 4) if v["maps"] else None}
        for v in player_deaths.values()
    ]
    kills_leader = max(player_kill_avg, key=lambda x: x["total_kills"], default=None) if player_kill_avg else None
    return {
        "team": team,
        "series_count": len(series),
        "maps_count": maps_count,
        "last_5_series": series_list,
        "last_3_series_detail": series_list[:3],
        "per_map": {
            "kills": {"average": _avg(kills), "total": sum(v for v in kills if v is not None),
                      "coverage": {"non_null": len([v for v in kills if v is not None]), "denominator": len(kills), "required": maps_count}},
            "deaths": {"average": _avg(deaths), "total": sum(v for v in deaths if v is not None), "derived": True,
                       "coverage": {"non_null": len([v for v in deaths if v is not None]), "denominator": len(deaths), "required": maps_count}},
            "towers": {"average": _avg(towers), "total": sum(v for v in towers if v is not None),
                       "coverage": {"non_null": len([v for v in towers if v is not None]), "denominator": len(towers), "required": maps_count}},
            "inhibitors": {"average": _avg(inhibs), "total": sum(v for v in inhibs if v is not None),
                           "coverage": {"non_null": len([v for v in inhibs if v is not None]), "denominator": len(inhibs), "required": maps_count}},
            "total_map_kills": {"average": _avg(total_map_kills),
                                "coverage": {"non_null": len([v for v in total_map_kills if v is not None]), "denominator": len(total_map_kills), "required": maps_count}},
        },
        "map_duration": {
            "average_all": _avg(all_durations),
            "average_wins": _avg(win_durations),
            "average_losses": _avg(loss_durations),
            "coverage": {"non_null": len(all_durations), "denominator": maps_count, "required": maps_count},
        },
        "players": {
            "kills_per_map": player_kill_avg,
            "deaths_per_map": player_death_avg,
            "kills_leader": kills_leader,
        },
    }


def _lol_statistics(session, event_key, event) -> dict:
    cutoff = _as_utc(event.kickoff_utc)
    a, b = event.team_a, event.team_b
    blocks = {}
    for team, other in ((a, b), (b, a)):
        if team:
            blocks[team] = _lol_team_block(session, team, other, cutoff)
    complete = all(v["series_count"] == LOL_SERIES_N for v in blocks.values()) and len(blocks) == 2
    # overall matchup kills leader
    leaders = [v["players"]["kills_leader"] for v in blocks.values() if v["players"]["kills_leader"]]
    overall_leader = max(leaders, key=lambda x: x["total_kills"], default=None) if leaders else None
    return {
        "sport": "lol",
        "event_key": event_key,
        "teams": [a, b],
        "cutoff_utc": cutoff.isoformat() if cutoff else None,
        "window": "last-5 complete LolSeries before kickoff (anchor excluded)",
        "status": "complete" if complete else "incomplete",
        "team_stats": blocks,
        "matchup_kills_leader": overall_leader,
    }


# --------------------------------------------------------------------------
# Fingerprint + materialization
# --------------------------------------------------------------------------

def _fingerprint(session, event_key, event) -> str:
    parts = [event_key, str(_as_utc(event.kickoff_utc)), event.sport,
             str(event.team_a), str(event.team_b)]
    if event.sport == "football":
        wins = session.exec(
            select(EventTeamHistoryWindow.fixture_source_id, EventTeamHistoryWindow.team,
                   EventTeamHistoryWindow.rank)
            .where(EventTeamHistoryWindow.event_key == event_key)
            .order_by(EventTeamHistoryWindow.team, EventTeamHistoryWindow.rank)
        ).all()
        for sid, team, rank in wins:
            fx = session.exec(
                select(FootballFixtureStat).where(
                    FootballFixtureStat.provider == "fresh_football",
                    FootballFixtureStat.source_id == sid,
                )
            ).first()
            parts.append(f"{team}:{rank}:{sid}:{fx.updated_at if fx else 'x'}")
    else:
        cutoff = _as_utc(event.kickoff_utc)
        for team, other in ((event.team_a, event.team_b), (event.team_b, event.team_a)):
            if not team:
                continue
            for s in _lol_series_window(session, team, other, cutoff):
                parts.append(f"{team}:{s.match_id}:{s.updated_at}")
    raw = "|".join(parts)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def compute_event(session: Session, event_key: str, force: bool = False) -> dict:
    """Compute (or reuse cached) descriptive statistics for an event."""
    event = _event(session, event_key)
    if event is None:
        return {"status": "not_found", "event_key": event_key}
    fp = _fingerprint(session, event_key, event)
    existing = session.exec(
        select(EventStatisticsReadModel).where(
            EventStatisticsReadModel.event_key == event_key,
            EventStatisticsReadModel.sport == event.sport,
        )
    ).first()
    if existing and existing.input_fingerprint == fp and not force:
        payload = json.loads(existing.payload_json)
        payload["_cache"] = {"recomputed": False, "computed_at": existing.computed_at.isoformat()}
        return payload
    if event.sport == "football":
        payload = _football_statistics(session, event_key, event)
    elif event.sport == "lol":
        payload = _lol_statistics(session, event_key, event)
    else:
        return {"status": "unsupported_sport", "event_key": event_key, "sport": event.sport}
    now = datetime.now(UTC)
    coverage = {"status": payload.get("status")}
    row = existing or EventStatisticsReadModel(event_key=event_key, sport=event.sport, input_fingerprint=fp)
    row.status = payload.get("status", "ok")
    row.input_fingerprint = fp
    row.payload_json = json.dumps(payload, ensure_ascii=False, default=str)
    row.coverage_json = json.dumps(coverage)
    row.computed_at = now
    row.updated_at = now
    session.add(row)
    session.commit()
    payload["_cache"] = {"recomputed": True, "computed_at": now.isoformat()}
    return payload


def rebuild_all(session: Session) -> dict:
    """Recompute read-models for every football+lol event with a window/series."""
    events = session.exec(
        select(ImportedOdds.event_key, ImportedOdds.sport)
        .where(ImportedOdds.sport.in_(("football", "lol")), ImportedOdds.event_key.is_not(None))
        .distinct()
    ).all()
    seen = set()
    counts = {"football": 0, "lol": 0, "recomputed": 0}
    for ek, sport in events:
        if ek in seen:
            continue
        seen.add(ek)
        res = compute_event(session, ek)
        if res.get("sport") in counts:
            counts[res["sport"]] += 1
        if (res.get("_cache") or {}).get("recomputed"):
            counts["recomputed"] += 1
    return counts
