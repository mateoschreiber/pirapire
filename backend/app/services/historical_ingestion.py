"""Bounded, idempotent real-data ingestion coordinator (Phase 4B1).

Restricts every request to participants of the current (active) odds. Persists
only real, provider-published values; null is never replaced with zero. No
calculations, predictions or UI changes happen here.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from sqlmodel import Session, select

from ..config import settings
from ..models_football import (
    FootballFixturePlayerStat,
    FootballFixtureStat,
)
from ..models_imports import ImportedOdds
from ..models_lol import LolGameHistory, LolSeries
from ..models_sources import IntegrationProviderState, SourceRun
from ..sources.football.api_football import ApiFootballClient
from ..sources.football.thesportsdb import TheSportsDBClient
from . import provider_state, source_runs
from .secret_provider import SecretProvider

# Curated, verifiable identity anchors for the current active participants.
# API-Football national-team ids and TheSportsDB team ids were confirmed by
# live probes; unknown participants are simply skipped (no fabrication).
API_FOOTBALL_TEAM_IDS = {
    "Argentina": 26,
    "Switzerland": 15,
    "Suiza": 15,
}
THESPORTSDB_TEAM_NAMES = {
    "Argentina": "Argentina",
    "Switzerland": "Switzerland",
    "Suiza": "Switzerland",
}
FOOTBALL_BOOTSTRAP_REQUEST_CAP = 90
FINISHED_STATUSES = {"FT", "AET", "PEN"}
FOOTBALL_FIXTURES_PER_TEAM = 10


def active_participants(session: Session) -> dict[str, set[str]]:
    rows = session.exec(select(ImportedOdds).where(ImportedOdds.is_current)).all()
    out: dict[str, set[str]] = {"football": set(), "lol": set()}
    for row in rows:
        if row.sport in out:
            out[row.sport].update(x for x in (row.team_a, row.team_b) if x)
    return out


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _to_int(value):
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip()
    if text == "" or text == "None":
        return None
    m = re.match(r"^-?\d+", text)
    return int(m.group()) if m else None


def _provider_errors(result: dict):
    data = result.get("data") if result else None
    if not isinstance(data, dict):
        return None
    errors = data.get("errors")
    if isinstance(errors, dict) and errors:
        return errors
    if isinstance(errors, list) and errors:
        return {"_": errors}
    return None


# --------------------------------------------------------------------------
# API-Football
# --------------------------------------------------------------------------

_STAT_MAP = {
    "corner kicks": "corners",
    "total shots": "shots_total",
    "shots on goal": "shots_on_target",
    "fouls": "fouls",
    "yellow cards": "yellow_cards",
    "red cards": "red_cards",
}


def _fixture_seasons() -> list[int]:
    # Free plans only expose a limited range of seasons; request newest first.
    configured = getattr(settings, "api_football_seasons", "") or ""
    seasons = [int(x) for x in re.findall(r"\d{4}", configured)]
    if not seasons:
        seasons = [2024, 2023, 2022]
    return sorted(set(seasons), reverse=True)


def _collect_recent_finished(client: ApiFootballClient, team_id: int, log) -> list[dict]:
    """Return up to FOOTBALL_FIXTURES_PER_TEAM finished fixtures, most recent first."""
    collected: dict[int, dict] = {}
    for season in _fixture_seasons():
        if client.budget_exhausted:
            break
        result = client.get_team_fixtures(team_id, season)
        if not result.get("ok"):
            log("warning", f"api_football fixtures team={team_id} season={season} status={result.get('status')} err={result.get('error')}")
            if result.get("error") == "budget_exhausted":
                break
            continue
        errors = _provider_errors(result)
        if errors:
            # Season-level restrictions (e.g. free-plan season) skip only that
            # season; a real rate/token error stops further requests.
            joined = " ".join(str(v).lower() for v in errors.values()) if isinstance(errors, dict) else str(errors).lower()
            if any(word in joined for word in ("rate", "limit", "token", "subscription", "quota")):
                client.budget_exhausted = True
                log("warning", f"api_football quota/token error team={team_id}; stopping")
                break
            log("info", f"api_football season {season} not accessible on plan; skipping season")
            continue
        for item in ApiFootballClient.response_list(result):
            fx = item.get("fixture") or {}
            fid = fx.get("id")
            status = ((fx.get("status") or {}).get("short")) or ""
            if fid is None or status not in FINISHED_STATUSES:
                continue
            collected[int(fid)] = item
    ordered = sorted(
        collected.values(),
        key=lambda it: ((it.get("fixture") or {}).get("date") or ""),
        reverse=True,
    )
    return ordered[:FOOTBALL_FIXTURES_PER_TEAM]


def _existing_fixture_complete(session: Session, fixture_id: str) -> bool:
    rows = session.exec(
        select(FootballFixtureStat).where(
            FootballFixtureStat.provider == "api_football",
            FootballFixtureStat.fixture_id == fixture_id,
        )
    ).all()
    if len(rows) < 2:
        return False
    return all(r.stats_present and r.events_present for r in rows)


def _parse_dt(value):
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _team_stats_from_response(stats_resp: list) -> dict[int, dict]:
    """Map team_external_id -> {field: value} from fixtures/statistics."""
    out: dict[int, dict] = {}
    for block in stats_resp:
        team = block.get("team") or {}
        tid = team.get("id")
        if tid is None:
            continue
        fields: dict = {}
        for stat in block.get("statistics") or []:
            key = _STAT_MAP.get(str(stat.get("type") or "").strip().lower())
            if key:
                fields[key] = _to_int(stat.get("value"))
        out[int(tid)] = fields
    return out


def _regulation_penalties_from_events(events_resp: list) -> dict[int, dict]:
    """Count regulation-time penalty goals per team from fixtures/events.

    Penalty shootout goals carry ``comments == 'Penalty Shootout'`` and are
    deliberately excluded so shootouts never count as penalties for/against.
    """
    out: dict[int, dict] = {}
    for ev in events_resp:
        team = ev.get("team") or {}
        tid = team.get("id")
        if tid is None:
            continue
        tid = int(tid)
        bucket = out.setdefault(tid, {"penalties_scored": 0, "penalties_missed": 0})
        etype = str(ev.get("type") or "").strip().lower()
        detail = str(ev.get("detail") or "").strip().lower()
        comments = str(ev.get("comments") or "").strip().lower()
        if "shootout" in comments:
            continue
        if etype == "goal" and detail == "penalty":
            bucket["penalties_scored"] += 1
        elif etype == "goal" and detail == "missed penalty":
            bucket["penalties_missed"] += 1
    return out


def _upsert_fixture_team_stat(session, provider, fid, side, payload) -> int:
    key = f"{provider}|{fid}|{side}"
    row = session.exec(
        select(FootballFixtureStat).where(FootballFixtureStat.source_key == key)
    ).first()
    is_new = row is None
    row = row or FootballFixtureStat(provider=provider, fixture_id=fid, team_side=side, source_key=key)
    for field, value in payload.items():
        setattr(row, field, value)
    row.updated_at = datetime.now(UTC)
    if is_new:
        row.fetched_at = datetime.now(UTC)
    session.add(row)
    return 1 if is_new else 0


def _upsert_fixture_player_stat(session, fid, payload) -> int:
    key = payload["source_key"]
    row = session.exec(
        select(FootballFixturePlayerStat).where(FootballFixturePlayerStat.source_key == key)
    ).first()
    if row is not None:
        return 0
    session.add(FootballFixturePlayerStat(**payload))
    return 1


def _ingest_fixture_detail(session, client, fid, log) -> tuple[bool, bool, int]:
    """Fetch stats/events/players for a fixture once. Returns (stats_ok, events_ok, players_inserted)."""
    stats_ok = events_ok = False
    players_inserted = 0
    team_stats: dict[int, dict] = {}
    pens: dict[int, dict] = {}

    st = client.get_fixture_statistics(fid)
    if st.get("ok") and not ApiFootballClient.has_provider_errors(st):
        team_stats = _team_stats_from_response(ApiFootballClient.response_list(st))
        stats_ok = bool(team_stats)
    ev = client.get_fixture_events(fid)
    if ev.get("ok") and not ApiFootballClient.has_provider_errors(ev):
        pens = _regulation_penalties_from_events(ApiFootballClient.response_list(ev))
        events_ok = True

    # Attach detail to the two existing fixture team rows.
    rows = session.exec(
        select(FootballFixtureStat).where(
            FootballFixtureStat.provider == "api_football",
            FootballFixtureStat.fixture_id == str(fid),
        )
    ).all()
    for row in rows:
        tid = _to_int(row.team_external_id)
        fields = team_stats.get(tid, {}) if tid is not None else {}
        for field, value in fields.items():
            setattr(row, field, value)
        if tid is not None and tid in pens:
            row.penalties_scored = pens[tid]["penalties_scored"]
            row.penalties_missed = pens[tid]["penalties_missed"]
        row.stats_present = row.stats_present or stats_ok
        row.events_present = row.events_present or events_ok
        row.updated_at = datetime.now(UTC)
        session.add(row)
    session.commit()

    pl = client.get_fixture_players(fid)
    if pl.get("ok") and not ApiFootballClient.has_provider_errors(pl):
        for block in ApiFootballClient.response_list(pl):
            team_name = (block.get("team") or {}).get("name")
            for pblock in block.get("players") or []:
                player = pblock.get("player") or {}
                stat = (pblock.get("statistics") or [{}])[0]
                fouls = stat.get("fouls") or {}
                cards = stat.get("cards") or {}
                shots = stat.get("shots") or {}
                penalty = stat.get("penalty") or {}
                pid = player.get("id")
                payload = {
                    "provider": "api_football",
                    "fixture_id": str(fid),
                    "team_name": team_name,
                    "player_external_id": str(pid) if pid is not None else None,
                    "player_name": player.get("name"),
                    "fouls_committed": _to_int(fouls.get("committed")),
                    "fouls_drawn": _to_int(fouls.get("drawn")),
                    "yellow_cards": _to_int(cards.get("yellow")),
                    "red_cards": _to_int(cards.get("red")),
                    "shots_total": _to_int(shots.get("total")),
                    "shots_on_target": _to_int(shots.get("on")),
                    "penalties_scored": _to_int(penalty.get("scored")),
                    "penalties_missed": _to_int(penalty.get("missed")),
                    "source_key": f"api_football|{fid}|{pid}",
                }
                if payload["player_external_id"] is None:
                    continue
                players_inserted += _upsert_fixture_player_stat(session, fid, payload)
        session.commit()
    return stats_ok, events_ok, players_inserted


def _ingest_api_football(session, run, participants, log) -> dict:
    api_key, source = SecretProvider.get_secret("api_football", "api_key", session=session, mark_used=True)
    if not api_key:
        provider_state.record(session, "api_football", "unconfigured")
        log("info", "API-Football unconfigured; continue with TheSportsDB only")
        return {"source": source, "status": "unconfigured", "requests": 0, "fixtures": 0, "teams": 0, "cursor": None}

    state = _get_state(session, "api_football")
    cursor = json.loads(state.cursor_json) if state.cursor_json else {}
    done_teams = set(cursor.get("done_teams") or [])

    client = ApiFootballClient(
        api_key,
        settings.api_football_base_url,
        request_delay=getattr(settings, "api_football_request_delay_seconds", 1.0),
        max_requests=getattr(settings, "api_football_bootstrap_request_cap", FOOTBALL_BOOTSTRAP_REQUEST_CAP),
        log_callback=log,
    )
    fixtures_seen = 0
    teams_done_now = 0
    pending: list[str] = []
    for name in sorted(participants):
        tid = API_FOOTBALL_TEAM_IDS.get(name)
        if tid is None:
            log("info", f"api_football no verified team id for '{name}'; skipped")
            continue
        if name in done_teams:
            continue
        if client.budget_exhausted:
            pending.append(name)
            continue
        fixtures = _collect_recent_finished(client, tid, log)
        for item in fixtures:
            fx = item.get("fixture") or {}
            fid = int(fx["id"])
            teams_blk = item.get("teams") or {}
            goals = item.get("goals") or {}
            score = item.get("score") or {}
            ht = score.get("halftime") or {}
            league = item.get("league") or {}
            home = teams_blk.get("home") or {}
            away = teams_blk.get("away") or {}
            kickoff = _parse_dt(fx.get("date"))
            status = (fx.get("status") or {}).get("short")
            for side, team, opp, gf, ga, htf, hta in (
                ("home", home, away, goals.get("home"), goals.get("away"), ht.get("home"), ht.get("away")),
                ("away", away, home, goals.get("away"), goals.get("home"), ht.get("away"), ht.get("home")),
            ):
                winner = team.get("winner")
                result = "W" if winner is True else ("L" if winner is False else "D")
                _upsert_fixture_team_stat(session, "api_football", str(fid), side, {
                    "team_external_id": str(team.get("id")) if team.get("id") is not None else None,
                    "team_name": team.get("name"),
                    "opponent_name": opp.get("name"),
                    "competition_name": league.get("name"),
                    "season": str(league.get("season")) if league.get("season") is not None else None,
                    "kickoff_utc": kickoff,
                    "match_status": status,
                    "is_home": side == "home",
                    "goals_for": _to_int(gf),
                    "goals_against": _to_int(ga),
                    "ht_goals_for": _to_int(htf),
                    "ht_goals_against": _to_int(hta),
                    "result": result,
                    "source_external_id": str(fid),
                })
            session.commit()
            fixtures_seen += 1
            if not client.budget_exhausted and not _existing_fixture_complete(session, str(fid)):
                _ingest_fixture_detail(session, client, fid, log)
        if client.budget_exhausted:
            pending.append(name)
        else:
            done_teams.add(name)
            teams_done_now += 1
    new_cursor = {"done_teams": sorted(done_teams), "pending": sorted(set(pending))}
    status = "success" if not pending else "partial"
    provider_state.record(
        session, "api_football", status,
        request_count=client.request_count,
        records_processed=fixtures_seen,
        coverage={"fixtures": fixtures_seen, "teams_completed": len(done_teams)},
    )
    _set_cursor(session, "api_football", new_cursor)
    log("info", f"api_football source={source} requests={client.request_count} fixtures={fixtures_seen} pending={pending}")
    return {"source": source, "status": status, "requests": client.request_count, "fixtures": fixtures_seen, "teams": teams_done_now, "cursor": new_cursor}


# --------------------------------------------------------------------------
# TheSportsDB (partial evidence for resolved matches)
# --------------------------------------------------------------------------

def _ingest_thesportsdb(session, run, participants, log) -> dict:
    api_key, source = SecretProvider.get_secret("thesportsdb", "api_key", session=session, mark_used=True)
    if not api_key:
        api_key, source = settings.thesportsdb_free_key, "public_free"
    client = TheSportsDBClient(
        api_key,
        request_delay=settings.thesportsdb_request_delay_seconds,
        cache_ttl_seconds=settings.thesportsdb_cache_ttl_seconds,
        log_callback=log,
    )
    inserted = 0
    events_seen = 0
    for name in sorted(participants):
        search_name = THESPORTSDB_TEAM_NAMES.get(name, name)
        team_res = client.search_teams(search_name)
        team_id = None
        if team_res.get("ok"):
            for t in (team_res.get("data") or {}).get("teams") or []:
                if (t.get("strSport") or "").lower() in ("soccer", "football") and _norm(t.get("strTeam")) == _norm(search_name):
                    team_id = t.get("idTeam")
                    break
        if not team_id:
            log("info", f"thesportsdb no unambiguous team for '{name}'")
            continue
        last = client.events_last(team_id)
        if not last.get("ok"):
            log("warning", f"thesportsdb eventslast team={team_id} status={last.get('status')}")
            continue
        results = (last.get("data") or {}).get("results") or []
        for ev in results:
            status = str(ev.get("strStatus") or "").upper()
            if status not in ("FT", "MATCH FINISHED", "AET", "PEN") and not (ev.get("intHomeScore") is not None):
                continue
            eid = ev.get("idEvent")
            if not eid:
                continue
            events_seen += 1
            stats_res = client.lookup_event_stats(eid)
            stat_by_type = {}
            if stats_res.get("ok"):
                for s in (stats_res.get("data") or {}).get("eventstats") or []:
                    stat_by_type[str(s.get("strStat") or "").strip().lower()] = s
            home_name = ev.get("strHomeTeam")
            away_name = ev.get("strAwayTeam")
            for side, tname, oname, gf, ga in (
                ("home", home_name, away_name, ev.get("intHomeScore"), ev.get("intAwayScore")),
                ("away", away_name, home_name, ev.get("intAwayScore"), ev.get("intHomeScore")),
            ):
                key = f"thesportsdb|{eid}|{side}"
                row = session.exec(select(FootballFixtureStat).where(FootballFixtureStat.source_key == key)).first()
                is_new = row is None
                row = row or FootballFixtureStat(provider="thesportsdb", fixture_id=str(eid), team_side=side, source_key=key)
                row.team_name = tname
                row.opponent_name = oname
                row.competition_name = ev.get("strLeague")
                row.season = ev.get("strSeason")
                row.kickoff_utc = _parse_dt((ev.get("strTimestamp") or ev.get("dateEvent")))
                row.match_status = ev.get("strStatus")
                row.is_home = side == "home"
                row.goals_for = _to_int(gf)
                row.goals_against = _to_int(ga)
                row.source_external_id = str(eid)
                shots_on = stat_by_type.get("shots on goal")
                shots_total = stat_by_type.get("total shots")
                if shots_on:
                    row.shots_on_target = _to_int(shots_on.get("intHome") if side == "home" else shots_on.get("intAway"))
                if shots_total:
                    row.shots_total = _to_int(shots_total.get("intHome") if side == "home" else shots_total.get("intAway"))
                row.stats_present = row.stats_present or bool(stat_by_type)
                row.updated_at = datetime.now(UTC)
                if is_new:
                    row.fetched_at = datetime.now(UTC)
                    inserted += 1
                session.add(row)
            session.commit()
    provider_state.record(
        session, "thesportsdb", "success",
        request_count=client.request_count,
        records_processed=inserted,
        coverage={"resolved_events": events_seen, "evidence_rows": inserted},
    )
    log("info", f"thesportsdb source={source} requests={client.request_count} events={events_seen} evidence_rows={inserted}")
    return {"source": source, "requests": client.request_count, "events": events_seen, "evidence_rows": inserted}


# --------------------------------------------------------------------------
# Leaguepedia (gated single query; no retry on 429)
# --------------------------------------------------------------------------

def _get_state(session, slug) -> IntegrationProviderState:
    row = session.exec(
        select(IntegrationProviderState).where(IntegrationProviderState.provider_slug == slug)
    ).first()
    if row is None:
        row = IntegrationProviderState(provider_slug=slug)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row


def _set_cursor(session, slug, cursor: dict) -> None:
    row = _get_state(session, slug)
    row.cursor_json = json.dumps(cursor, sort_keys=True)
    session.add(row)
    session.commit()


def _ingest_leaguepedia(session, run, participants, log) -> dict:
    from datetime import timedelta

    state = _get_state(session, "leaguepedia")
    now = datetime.now(UTC)
    nra = state.next_retry_at
    if nra is not None:
        if nra.tzinfo is None:
            nra = nra.replace(tzinfo=UTC)
        if nra > now:
            log("info", f"leaguepedia gated until {nra.isoformat()}; skipped")
            return {"status": "gated", "series": 0, "maps_linked": 0, "next_retry_at": nra.isoformat()}

    from urllib.error import HTTPError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen

    start = (now - timedelta(days=settings.leaguepedia_import_lookback_days)).strftime("%Y-%m-%d %H:%M:%S")
    end = (now + timedelta(days=settings.leaguepedia_import_lookahead_days)).strftime("%Y-%m-%d %H:%M:%S")
    q = chr(34)
    where = "SG.DateTime_UTC >= " + q + start + q + " AND SG.DateTime_UTC <= " + q + end + q
    params = {
        "tables": "ScoreboardGames=SG",
        "fields": "SG.MatchId,SG.GameId,SG.N_GameInMatch,SG.DateTime_UTC,SG.Team1,SG.Team2,SG.Winner,SG.OverviewPage",
        "where": where,
        "format": "json",
        "limit": "200",
    }
    url = settings.leaguepedia_base_url + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": settings.leaguepedia_user_agent})

    def _rate_limit(reason: str):
        state.next_retry_at = now + timedelta(hours=6)
        state.status = "rate_limited"
        state.last_error_code = "quota_exceeded"
        state.last_checked_at = now
        session.add(state)
        session.commit()
        log("warning", f"leaguepedia {reason}; next_retry_at set +6h; no retry")
        return {"status": "rate_limited", "series": 0, "maps_linked": 0, "next_retry_at": state.next_retry_at.isoformat()}

    try:
        with urlopen(req, timeout=25) as res:
            body = res.read().decode("utf-8", "replace")
    except HTTPError as exc:
        if exc.code == 429:
            return _rate_limit("HTTP 429")
        log("warning", f"leaguepedia HTTP {exc.code}; no retry")
        return {"status": "error", "series": 0, "maps_linked": 0}
    except Exception as exc:  # noqa: BLE001
        log("warning", f"leaguepedia unavailable: {type(exc).__name__}")
        return {"status": "error", "series": 0, "maps_linked": 0}

    try:
        rows = json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return _rate_limit("non-JSON response (ratelimited)")
    if isinstance(rows, dict) and rows.get("error"):
        return _rate_limit("cargo error (ratelimited)")
    if not isinstance(rows, list):
        log("warning", "leaguepedia unexpected structure; no retry")
        return {"status": "error", "series": 0, "maps_linked": 0}

    part_norm = {_norm(p) for p in participants}
    series_new = 0
    maps_linked = 0
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        mid = str(row.get("MatchId") or "").strip()
        if not mid:
            continue
        if part_norm and not ({_norm(row.get("Team1")), _norm(row.get("Team2"))} & part_norm):
            continue
        grouped.setdefault(mid, []).append(row)

    for mid, maps in grouped.items():
        first = maps[0]
        skey = "leaguepedia|" + mid
        srow = session.exec(select(LolSeries).where(LolSeries.source_key == skey)).first()
        is_new = srow is None
        srow = srow or LolSeries(source_name="leaguepedia", match_id=mid, source_key=skey)
        srow.overview_page = first.get("OverviewPage")
        srow.tournament = first.get("OverviewPage")
        srow.team1 = first.get("Team1")
        srow.team2 = first.get("Team2")
        srow.date = str(first.get("DateTime UTC") or "")
        srow.n_games = len(maps)
        srow.updated_at = now
        if is_new:
            srow.fetched_at = now
            series_new += 1
        session.add(srow)
        session.commit()
        # link existing maps to the confirmed MatchId
        for m in maps:
            gid = str(m.get("GameId") or "").strip()
            if not gid:
                continue
            game = session.exec(
                select(LolGameHistory).where(
                    LolGameHistory.source_name == "leaguepedia",
                    LolGameHistory.source_game_id == gid,
                )
            ).first()
            if game is not None:
                game.match_id = mid
                game.n_game_in_match = _to_int(m.get("N GameInMatch") or m.get("N_GameInMatch"))
                game.updated_at = now
                session.add(game)
                maps_linked += 1
        session.commit()

    state.next_retry_at = None
    provider_state.record(
        session, "leaguepedia", "success",
        request_count=1,
        records_processed=series_new + maps_linked,
        coverage={"series": series_new, "maps_linked": maps_linked},
    )
    log("info", f"leaguepedia series={series_new} maps_linked={maps_linked}")
    return {"status": "success", "series": series_new, "maps_linked": maps_linked}


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------

def run(session: Session) -> dict:
    """One bounded, idempotent ingestion pass restricted to active participants."""
    active = session.exec(
        select(SourceRun).where(SourceRun.status.in_(("running", "pending")))
    ).first()
    participants = active_participants(session)
    if active is not None:
        return {
            "status": "skipped_active_run",
            "active_run_id": active.id,
            "football_participants": len(participants["football"]),
            "lol_participants": len(participants["lol"]),
            "api_football": "skipped_active_run",
            "at": datetime.now(UTC).isoformat(),
        }
    if not getattr(settings, "phase4b_live_ingestion", True):
        api_key, source = SecretProvider.get_secret("api_football", "api_key", session=session)
        return {
            "status": "live_ingestion_disabled",
            "football_participants": len(participants["football"]),
            "lol_participants": len(participants["lol"]),
            "api_football": source,
            "api_football_status": "disabled",
            "at": datetime.now(UTC).isoformat(),
        }

    football_run = source_runs.create_run(session, "football", "historical_ingestion", "scheduled")

    def flog(level, msg):
        source_runs.log(session, football_run, level, msg)

    tsdb = _ingest_thesportsdb(session, football_run, participants["football"], flog)
    api = _ingest_api_football(session, football_run, participants["football"], flog)
    football_status = "partial" if api.get("status") in ("partial", "unconfigured") else "success"
    source_runs.finalize(
        session, football_run, football_status,
        message=f"api_football={api.get('status')}; tsdb_evidence={tsdb.get('evidence_rows')}",
        inserted=tsdb.get("evidence_rows", 0) + api.get("fixtures", 0),
    )

    lol_run = source_runs.create_run(session, "lol", "historical_ingestion", "scheduled")

    def llog(level, msg):
        source_runs.log(session, lol_run, level, msg)

    lp = _ingest_leaguepedia(session, lol_run, participants["lol"], llog)
    lol_status = "success" if lp.get("status") in ("success", "gated") else "partial"
    source_runs.finalize(
        session, lol_run, lol_status,
        message=f"leaguepedia={lp.get('status')}; series={lp.get('series')}",
        inserted=lp.get("series", 0),
    )

    return {
        "football_participants": len(participants["football"]),
        "lol_participants": len(participants["lol"]),
        "api_football": api.get("source", "unconfigured"),
        "api_football_status": api.get("status"),
        "api_football_requests": api.get("requests", 0),
        "api_football_fixtures": api.get("fixtures", 0),
        "thesportsdb_evidence_rows": tsdb.get("evidence_rows", 0),
        "leaguepedia": lp.get("status"),
        "leaguepedia_series": lp.get("series", 0),
        "at": datetime.now(UTC).isoformat(),
    }
