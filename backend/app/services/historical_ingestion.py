"""Bounded, idempotent real-data ingestion coordinator (Phase 4B1).

Restricts every request to participants of the current (active) odds. Persists
only real, provider-published values; null is never replaced with zero. No
calculations, predictions or UI changes happen here.
"""
from __future__ import annotations

import json
import re
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from ..config import settings
from ..models_football import (
    FootballFixturePlayerStat,
    FootballFixtureStat,
)
from ..models_imports import ImportedOdds
from ..models_lol import LolGameHistory, LolPlayerGameStat, LolSeries, LolTeamGameStat
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
    "offsides": "offsides",
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
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


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
                    "source": "api_football",
                    "source_url": f"{settings.api_football_base_url.rstrip('/')}/fixtures?id={fid}",
                    "source_id": str(fid),
                    "observed_at": datetime.now(UTC),
                    "data_as_of": kickoff,
                    "freshness_class": "historical_fallback",
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
# Football freshness (staleness marking + last-N eligibility)
# --------------------------------------------------------------------------

def _kickoff_for_football_team(session, team_name):
    row = session.exec(
        select(ImportedOdds.kickoff_utc)
        .where(ImportedOdds.is_current, ImportedOdds.sport == "football")
        .where((ImportedOdds.team_a == team_name) | (ImportedOdds.team_b == team_name))
    ).first()
    if row is None:
        return None
    kickoff = row[0] if isinstance(row, tuple) else row
    if kickoff is not None and kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=UTC)
    return kickoff


def _most_recent_real_match_date(session, participant, log) -> datetime | None:
    """Use TheSportsDB eventslast to find the most recent real match date.

    This is a freshness signal only: a more recent published match proves that
    the API-Football 2022-2024 rows are historical fallback (stale).
    """
    api_key, _ = SecretProvider.get_secret("thesportsdb", "api_key", session=session)
    if not api_key:
        api_key = settings.thesportsdb_free_key
    client = TheSportsDBClient(api_key, request_delay=settings.thesportsdb_request_delay_seconds,
                               cache_ttl_seconds=settings.thesportsdb_cache_ttl_seconds, log_callback=log)
    search_name = THESPORTSDB_TEAM_NAMES.get(participant, participant)
    res = client.search_teams(search_name)
    team_id = None
    if res.get("ok"):
        for t in (res.get("data") or {}).get("teams") or []:
            if (t.get("strSport") or "").lower() in ("soccer", "football") and _norm(t.get("strTeam")) == _norm(search_name):
                team_id = t.get("idTeam")
                break
    if not team_id:
        return None
    last = client.events_last(team_id)
    if not last.get("ok"):
        return None
    best = None
    for ev in (last.get("data") or {}).get("results") or []:
        dt = _parse_dt((ev.get("strTimestamp") or ev.get("dateEvent") or "").replace(" ", "T"))
        if dt is not None and (best is None or dt > best):
            best = dt
    return best


def _football_freshness(session, participants, log) -> dict:
    """Mark staleness and last-10 eligibility for API-Football fixture rows.

    - eligible_for_last_n: exactly the 10 most recent FINISHED rows (by kickoff)
      for the team, strictly before the Aposta event kickoff.
    - historical_fallback_stale: rows whose kickoff is older than a more recent
      real match proven by another source (TheSportsDB eventslast).
    """
    report = {}
    for participant in sorted(participants):
        recent_real = _most_recent_real_match_date(session, participant, log)
        kickoff = _kickoff_for_football_team(session, participant)
        # Rows for this participant (either side).
        rows = session.exec(
            select(FootballFixtureStat).where(
                FootballFixtureStat.provider == "api_football",
                (FootballFixtureStat.team_name == participant) | (FootballFixtureStat.opponent_name == participant),
            )
        ).all()
        # Deduplicate to one perspective per fixture for ordering.
        by_fixture = {}
        for r in rows:
            by_fixture.setdefault(r.fixture_id, []).append(r)
        dated = []
        for fid, frows in by_fixture.items():
            k = frows[0].kickoff_utc
            if k is not None and k.tzinfo is None:
                k = k.replace(tzinfo=UTC)
            dated.append((k, fid, frows))
        # Order most recent first; only fixtures strictly before the event kickoff.
        def _before(k):
            return kickoff is None or (k is not None and k < kickoff)
        eligible_sorted = sorted(
            [d for d in dated if _before(d[0])],
            key=lambda x: (x[0] is not None, x[0] or datetime.min.replace(tzinfo=UTC)),
            reverse=True,
        )
        # candidate window = the 10 most recent before kickoff (best available).
        candidate_fids = {fid for _, fid, _ in eligible_sorted[:FOOTBALL_FIXTURES_PER_TEAM]}
        stale_count = 0
        eligible_count = 0
        candidate_count = 0
        for k, fid, frows in dated:
            in_candidate = fid in candidate_fids
            # Staleness: a newer real match exists than this row's kickoff.
            is_stale = (
                recent_real is not None and k is not None and k < recent_real
                and (recent_real - k).days > 30
            )
            # A stale row is NEVER eligible for calculations, only a candidate.
            is_eligible = in_candidate and not is_stale
            for r in frows:
                changed = False
                if r.candidate_last_n != in_candidate:
                    r.candidate_last_n = in_candidate
                    changed = True
                if r.eligible_for_last_n != is_eligible:
                    r.eligible_for_last_n = is_eligible
                    changed = True
                new_class = "historical_fallback_stale" if is_stale else "historical_fallback"
                if r.freshness_class != new_class:
                    r.freshness_class = new_class
                    changed = True
                if changed:
                    session.add(r)
            if is_eligible:
                eligible_count += 1
            if in_candidate:
                candidate_count += 1
            if is_stale:
                stale_count += 1
        session.commit()
        report[participant] = {
            "fixtures": len(by_fixture),
            "candidate_last_10": min(candidate_count, FOOTBALL_FIXTURES_PER_TEAM),
            "eligible_last_10": eligible_count,
            "stale": stale_count,
            "most_recent_real": recent_real.isoformat() if recent_real else None,
            "candidate_dates": [str(x[0]) for x in eligible_sorted[:FOOTBALL_FIXTURES_PER_TEAM]],
        }
    return report


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


LEAGUEPEDIA_BASE = "https://lol.fandom.com/wiki/Special:CargoExport"
SERIES_LAST_N = 10


def _leaguepedia_query(team_names: list[str], log):
    """One paginated Cargo call for a set of team names, DESC by date.

    Searches Team1 OR Team2 across all registered names, without a league
    filter or a short time window. Returns (rows|None, status).
    """
    from urllib.error import HTTPError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen

    q = chr(34)
    clauses = []
    for name in team_names:
        safe = name.replace(q, "")
        clauses.append(f"SG.Team1={q}{safe}{q}")
        clauses.append(f"SG.Team2={q}{safe}{q}")
    if not clauses:
        return [], "success"
    where = "(" + " OR ".join(clauses) + ")"
    params = {
        "tables": "ScoreboardGames=SG",
        "fields": "SG.MatchId,SG.GameId,SG.N_GameInMatch,SG.DateTime_UTC,SG.Team1,SG.Team2,SG.Winner,SG.OverviewPage",
        "where": where,
        "order_by": "SG.DateTime_UTC DESC",
        "format": "json",
        "limit": "100",
    }
    url = settings.leaguepedia_base_url + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": settings.leaguepedia_user_agent})
    try:
        with urlopen(req, timeout=25) as res:
            body = res.read().decode("utf-8", "replace")
    except HTTPError as exc:
        if exc.code == 429:
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            return None, ("rate_limited", retry_after)
        log("warning", f"leaguepedia HTTP {exc.code}; no retry")
        return None, "error"
    except Exception as exc:  # noqa: BLE001
        log("warning", f"leaguepedia unavailable: {type(exc).__name__}")
        return None, "error"
    try:
        rows = json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return None, ("rate_limited", None)
    if isinstance(rows, dict) and rows.get("error"):
        return None, ("rate_limited", None)
    if not isinstance(rows, list):
        log("warning", "leaguepedia unexpected structure; no retry")
        return None, "error"
    return rows, "success"


def _group_series(rows: list[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for row in rows:
        mid = str(row.get("MatchId") or "").strip()
        gid = str(row.get("GameId") or "").strip()
        if not mid or not gid:  # a series requires MatchId AND at least one GameId
            continue
        grouped.setdefault(mid, []).append(row)
    return grouped


def _cargo_get(tables: str, fields: str, where: str, log, order_by: str | None = None, limit: int = 100):
    """Generic single Cargo query. Returns (rows|None, status).

    status is "success", "error" or ("rate_limited", retry_after) for 429s and
    ratelimited/non-JSON bodies. Never retries in a loop.
    """
    from urllib.error import HTTPError
    from urllib.parse import urlencode
    from urllib.request import Request, urlopen

    params = {"tables": tables, "fields": fields, "where": where, "format": "json", "limit": str(limit)}
    if order_by:
        params["order_by"] = order_by
    url = settings.leaguepedia_base_url + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": settings.leaguepedia_user_agent})
    try:
        with urlopen(req, timeout=25) as res:
            body = res.read().decode("utf-8", "replace")
    except HTTPError as exc:
        if exc.code == 429:
            retry_after = exc.headers.get("Retry-After") if exc.headers else None
            return None, ("rate_limited", retry_after)
        log("warning", f"leaguepedia cargo HTTP {exc.code}; no retry")
        return None, "error"
    except Exception as exc:  # noqa: BLE001
        log("warning", f"leaguepedia cargo unavailable: {type(exc).__name__}")
        return None, "error"
    try:
        rows = json.loads(body)
    except (ValueError, json.JSONDecodeError):
        return None, ("rate_limited", None)
    if isinstance(rows, dict) and rows.get("error"):
        return None, ("rate_limited", None)
    if not isinstance(rows, list):
        return None, "error"
    return rows, "success"


SG_MAP_FIELDS = (
    "SG.MatchId,SG.GameId,SG.N_GameInMatch,SG.DateTime_UTC,SG.Tournament,SG.OverviewPage,"
    "SG.Team1,SG.Team2,SG.Winner,SG.WinTeam,SG.LossTeam,SG.Gamelength_Number,"
    "SG.Team1Kills,SG.Team2Kills,SG.Team1Towers,SG.Team2Towers,"
    "SG.Team1Inhibitors,SG.Team2Inhibitors,SG.Team1Dragons,SG.Team2Dragons,"
    "SG.Team1Barons,SG.Team2Barons,SG.Patch"
)
SP_FIELDS = "SP.GameId,SP.Name,SP.Link,SP.Team,SP.Role,SP.Champion,SP.Kills,SP.Deaths,SP.Assists,SP.CS,SP.Gold"
MAP_SOURCE = "leaguepedia_map"


def _gamelength_seconds(value):
    n = value
    try:
        minutes = float(n)
    except (TypeError, ValueError):
        return None
    return int(round(minutes * 60))


def _upsert_map_game(session, m, now) -> tuple[bool, bool, bool]:
    """Persist one map to LolGameHistory + two LolTeamGameStat rows.

    Returns (game_new, team_rows_new_any, had_result).
    """
    mid = str(m.get("MatchId") or "").strip()
    gid = str(m.get("GameId") or "").strip()
    if not mid or not gid:
        return (False, False, False)
    date_dt = _parse_dt(str(m.get("DateTime UTC") or "").replace(" ", "T"))
    date_iso = date_dt.isoformat() if date_dt else None
    team1 = m.get("Team1")
    team2 = m.get("Team2")
    win_team = m.get("WinTeam")
    winner_num = _to_int(m.get("Winner"))
    winner_team = win_team or (team1 if winner_num == 1 else (team2 if winner_num == 2 else None))
    length_s = _gamelength_seconds(m.get("Gamelength Number"))
    t1_kills = _to_int(m.get("Team1Kills"))
    t2_kills = _to_int(m.get("Team2Kills"))

    skey = f"{MAP_SOURCE}|{gid}"
    game = session.exec(
        select(LolGameHistory).where(
            LolGameHistory.source_name == MAP_SOURCE,
            LolGameHistory.source_game_id == gid,
        )
    ).first()
    game_new = game is None
    game = game or LolGameHistory(source_name=MAP_SOURCE, source_game_id=gid, source_key=skey)
    game.year = date_dt.year if date_dt else None
    game.league = m.get("OverviewPage")
    game.date = date_iso
    game.patch = m.get("Patch")
    game.game_number = _to_int(m.get("N GameInMatch"))
    game.n_game_in_match = _to_int(m.get("N GameInMatch"))
    game.match_id = mid
    game.game_length_seconds = length_s
    game.blue_team = team1
    game.red_team = team2
    game.winner_team = winner_team
    game.updated_at = now
    session.add(game)
    session.commit()
    session.refresh(game)

    team_new = False
    sides = (
        ("blue", team1, team2, t1_kills, t2_kills, _to_int(m.get("Team1Towers")), _to_int(m.get("Team1Inhibitors")), _to_int(m.get("Team1Dragons")), _to_int(m.get("Team1Barons"))),
        ("red", team2, team1, t2_kills, t1_kills, _to_int(m.get("Team2Towers")), _to_int(m.get("Team2Inhibitors")), _to_int(m.get("Team2Dragons")), _to_int(m.get("Team2Barons"))),
    )
    for side, team, opp, kills, opp_kills, towers, inhibs, dragons, barons in sides:
        tkey = f"{MAP_SOURCE}|{gid}|{team}"
        stat = session.exec(
            select(LolTeamGameStat).where(LolTeamGameStat.source_key == tkey)
        ).first()
        if stat is None:
            team_new = True
        stat = stat or LolTeamGameStat(source_name=MAP_SOURCE, source_game_id=gid, team_name=team, source_key=tkey)
        stat.game_id = game.id
        stat.year = date_dt.year if date_dt else None
        stat.league = m.get("OverviewPage")
        stat.date = date_iso
        stat.patch = m.get("Patch")
        stat.team_name = team
        stat.opponent_name = opp
        stat.side = side
        stat.result = 1 if (winner_team and team == winner_team) else (0 if winner_team else None)
        stat.team_kills = kills
        stat.team_deaths = opp_kills  # deaths == opponent kills (Leaguepedia has no team deaths field)
        stat.towers = towers
        stat.inhibitors = inhibs
        stat.dragons = dragons
        stat.barons = barons
        stat.game_length_seconds = length_s
        session.add(stat)
    session.commit()
    return (game_new, team_new, winner_team is not None)


def _upsert_map_players(session, gid, players, now) -> int:
    inserted = 0
    for p in players:
        pname = (p.get("Name") or "").strip()
        team = (p.get("Team") or "").strip()
        if not pname or not team:
            continue
        role = (p.get("Role") or "").strip().lower()
        pkey = f"{MAP_SOURCE}|{gid}|{pname}|{team}"
        existing = session.exec(
            select(LolPlayerGameStat).where(LolPlayerGameStat.source_key == pkey)
        ).first()
        if existing is not None:
            continue
        game = session.exec(
            select(LolGameHistory).where(
                LolGameHistory.source_name == MAP_SOURCE,
                LolGameHistory.source_game_id == gid,
            )
        ).first()
        session.add(LolPlayerGameStat(
            source_name=MAP_SOURCE,
            source_game_id=gid,
            game_id=game.id if game else None,
            team_name=team,
            player_name=pname,
            role=role,
            champion=p.get("Champion"),
            kills=_to_int(p.get("Kills")),
            deaths=_to_int(p.get("Deaths")),
            assists=_to_int(p.get("Assists")),
            cs=_to_int(p.get("CS")),
            gold=_to_int(p.get("Gold")),
            source_key=pkey,
        ))
        inserted += 1
    session.commit()
    return inserted


def _upsert_series(session, mid, maps, now, source_url) -> bool:
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
    srow.game_ids_json = json.dumps(sorted({str(m.get("GameId")) for m in maps if m.get("GameId")}))
    srow.source = "leaguepedia"
    srow.source_url = source_url
    srow.source_id = mid
    srow.observed_at = now
    srow.data_as_of = _parse_dt(str(first.get("DateTime UTC") or "").replace(" ", "T"))
    srow.freshness_class = "fresh"
    srow.updated_at = now
    if is_new:
        srow.fetched_at = now
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
    session.commit()
    return is_new


def _kickoff_for_lol_team(session, team_name):
    row = session.exec(
        select(ImportedOdds.kickoff_utc)
        .where(ImportedOdds.is_current, ImportedOdds.sport == "lol")
        .where((ImportedOdds.team_a == team_name) | (ImportedOdds.team_b == team_name))
    ).first()
    if row is None:
        return None
    kickoff = row[0] if isinstance(row, tuple) else row
    if kickoff is not None and kickoff.tzinfo is None:
        kickoff = kickoff.replace(tzinfo=UTC)
    return kickoff


def _mark_last_n_series(session, team_name, source_names, kickoff, now) -> dict:
    """Flag the last SERIES_LAST_N complete series (by date, before kickoff)."""
    norm_names = {_norm(n) for n in source_names} | {_norm(team_name)}
    candidates = session.exec(
        select(LolSeries).where(LolSeries.source_name == "leaguepedia")
    ).all()
    mine = []
    for s in candidates:
        if {_norm(s.team1), _norm(s.team2)} & norm_names:
            sdate = _parse_dt(str(s.date or "").replace(" ", "T"))
            if kickoff is not None and sdate is not None and sdate >= kickoff:
                continue  # only series strictly before kickoff
            mine.append((sdate, s))
    mine.sort(key=lambda x: (x[0] is not None, x[0] or datetime.min.replace(tzinfo=UTC)), reverse=True)
    # Only 'complete' series may be selected for the window.
    complete = [(d, s) for d, s in mine if s.series_status == "complete"]
    selected = complete[:SERIES_LAST_N]
    selected_ids = {s.id for _, s in selected}
    for _, s in mine:
        want = s.id in selected_ids
        if s.eligible_for_last_n != want:
            s.eligible_for_last_n = want
            session.add(s)
    session.commit()
    return {
        "team": team_name,
        "total_series": len(mine),
        "complete_series": len(complete),
        "eligible": len(selected),
        "selected_match_ids": [s.match_id for _, s in selected],
        "dates": [str(s.date) for _, s in selected],
    }


def _ingest_series_maps(session, series_list, log, state, rate_limit_cb) -> dict:
    """Fetch map facts + players for the given series' GameIds.

    Sequential, small batches, cache-aware (skips GameIds already stored). On
    429 persists cooldown and returns; never retries in a loop.
    """
    import time as _time

    now = datetime.now(UTC)
    q = chr(34)
    maps_new = team_rows_new = players_new = 0
    games_queried = 0
    batch_delay = getattr(settings, "leaguepedia_request_delay_seconds", 2.0)
    for srow in series_list:
        try:
            want_gids = set(json.loads(srow.game_ids_json or "[]"))
        except (ValueError, TypeError):
            want_gids = set()
        # Cache: only fetch maps that are not already stored with map facts.
        stored = set(session.exec(
            select(LolGameHistory.source_game_id).where(
                LolGameHistory.source_name == MAP_SOURCE,
                LolGameHistory.match_id == srow.match_id,
            )
        ).all())
        missing = sorted(want_gids - stored)
        if not missing:
            continue
        # ScoreboardGames map facts for the whole match (small: <=7 games).
        _time.sleep(batch_delay)
        where = f"SG.MatchId={q}{srow.match_id.replace(q, '')}{q}"
        rows, status = _cargo_get("ScoreboardGames=SG", SG_MAP_FIELDS, where, log,
                                  order_by="SG.N_GameInMatch ASC", limit=20)
        games_queried += 1
        if rows is None:
            if isinstance(status, tuple) and status[0] == "rate_limited":
                rate_limit_cb("429 on map facts", status[1])
                return {"maps_new": maps_new, "team_rows_new": team_rows_new,
                        "players_new": players_new, "games_queried": games_queried, "rate_limited": True}
            log("warning", f"map facts failed for {srow.match_id}; continuing")
            continue
        for m in rows:
            g_new, t_new, _ = _upsert_map_game(session, m, now)
            maps_new += 1 if g_new else 0
            team_rows_new += 1 if t_new else 0
        # Refresh the authoritative published GameId list + count from the map
        # query (the discovery query may have truncated).
        published_gids = sorted({str(m.get("GameId")) for m in rows if m.get("GameId")})
        if published_gids:
            srow.game_ids_json = json.dumps(published_gids)
            srow.n_games = len(published_gids)
            session.add(srow)
            session.commit()
        # ScoreboardPlayers in small GameId batches.
        gids = [str(m.get("GameId")) for m in rows if m.get("GameId")]
        for i in range(0, len(gids), 3):
            batch = gids[i:i + 3]
            clause = " OR ".join(f"SP.GameId={q}{g.replace(q, '')}{q}" for g in batch)
            _time.sleep(batch_delay)
            prows, pstatus = _cargo_get("ScoreboardPlayers=SP", SP_FIELDS, f"({clause})", log,
                                        order_by="SP.GameId ASC", limit=60)
            games_queried += 1
            if prows is None:
                if isinstance(pstatus, tuple) and pstatus[0] == "rate_limited":
                    rate_limit_cb("429 on players", pstatus[1])
                    return {"maps_new": maps_new, "team_rows_new": team_rows_new,
                            "players_new": players_new, "games_queried": games_queried, "rate_limited": True}
                continue
            by_gid: dict[str, list] = {}
            for pr in prows:
                by_gid.setdefault(str(pr.get("GameId")), []).append(pr)
            for g, plist in by_gid.items():
                players_new += _upsert_map_players(session, g, plist, now)
    return {"maps_new": maps_new, "team_rows_new": team_rows_new,
            "players_new": players_new, "games_queried": games_queried, "rate_limited": False}


def _update_series_status(session, srow) -> str:
    """Set series_status to complete/partial. Complete = a final result exists
    and every published GameId has map facts stored."""
    try:
        want_gids = set(json.loads(srow.game_ids_json or "[]"))
    except (ValueError, TypeError):
        want_gids = set()
    stored = set(session.exec(
        select(LolGameHistory.source_game_id).where(
            LolGameHistory.source_name == MAP_SOURCE,
            LolGameHistory.match_id == srow.match_id,
        )
    ).all())
    has_result = False
    if want_gids and want_gids <= stored:
        # Every published map is stored; a series result is implied when each
        # stored map has a winner.
        winners = session.exec(
            select(LolGameHistory.winner_team).where(
                LolGameHistory.source_name == MAP_SOURCE,
                LolGameHistory.match_id == srow.match_id,
            )
        ).all()
        has_result = all(winners) and len(winners) > 0
    status = "complete" if (want_gids and want_gids <= stored and has_result) else "partial"
    if srow.series_status != status:
        srow.series_status = status
        session.add(srow)
        session.commit()
    return status


def _ingest_leaguepedia(session, run, participants, log) -> dict:
    from datetime import timedelta

    from .lol_team_aliases import leaguepedia_query_names, seed_leaguepedia_aliases

    state = _get_state(session, "leaguepedia")
    now = datetime.now(UTC)
    nra = state.next_retry_at
    if nra is not None:
        if nra.tzinfo is None:
            nra = nra.replace(tzinfo=UTC)
        if nra > now:
            log("info", f"leaguepedia gated until {nra.isoformat()}; skipped")
            return {"status": "gated", "series": 0, "teams": {}, "next_retry_at": nra.isoformat()}

    seed_leaguepedia_aliases(session)

    def _rate_limit(reason, retry_after=None):
        try:
            cooldown = float(retry_after) if retry_after else 6 * 3600
        except (TypeError, ValueError):
            cooldown = 6 * 3600
        state.next_retry_at = now + timedelta(seconds=cooldown)
        state.status = "rate_limited"
        state.last_error_code = "quota_exceeded"
        state.last_checked_at = now
        session.add(state)
        session.commit()
        log("warning", f"leaguepedia {reason}; next_retry_at={state.next_retry_at.isoformat()}; no retry")
        return {"status": "rate_limited", "series": 0, "teams": {}, "next_retry_at": state.next_retry_at.isoformat()}

    # One sequential, rate-limited query per participant within this window.
    # Each participant is searched by all of its registered Leaguepedia names in
    # Team1 OR Team2, ordered DESC. Stops immediately on the first 429.
    series_new = 0
    resolution: dict[str, list[str]] = {}
    requests = 0
    import time as _time
    for idx, name in enumerate(sorted(participants)):
        names = leaguepedia_query_names(session, name) or [name]
        resolution[name] = names
        if idx > 0:
            _time.sleep(getattr(settings, "leaguepedia_request_delay_seconds", 2.0))
        rows, status = _leaguepedia_query(names, log)
        requests += 1
        if rows is None:
            if isinstance(status, tuple) and status[0] == "rate_limited":
                return _rate_limit("429/ratelimited", status[1])
            log("warning", f"leaguepedia query failed for {name}; continuing")
            continue
        for mid, maps in _group_series(rows).items():
            if _upsert_series(session, mid, maps, now, LEAGUEPEDIA_BASE):
                series_new += 1

    # Candidate window per participant: the most recent SERIES_LAST_N series by
    # date, strictly before kickoff. These are the only series whose maps we
    # fetch (bounded work).
    candidate_series: dict[int, "LolSeries"] = {}
    for name in sorted(participants):
        kickoff = _kickoff_for_lol_team(session, name)
        norm_names = {_norm(n) for n in resolution.get(name, [name])} | {_norm(name)}
        mine = []
        for s in session.exec(select(LolSeries).where(LolSeries.source_name == "leaguepedia")).all():
            if {_norm(s.team1), _norm(s.team2)} & norm_names:
                sdate = _parse_dt(str(s.date or "").replace(" ", "T"))
                if kickoff is not None and sdate is not None and sdate >= kickoff:
                    continue
                mine.append((sdate, s))
        mine.sort(key=lambda x: (x[0] is not None, x[0] or datetime.min.replace(tzinfo=UTC)), reverse=True)
        for _, s in mine[:SERIES_LAST_N]:
            candidate_series[s.id] = s

    # Ingest map facts + players for the candidate series (sequential, cached).
    map_stats = _ingest_series_maps(session, list(candidate_series.values()), log, state, _rate_limit)
    for srow in candidate_series.values():
        _update_series_status(session, srow)

    # Now flag exactly the last SERIES_LAST_N *complete* series per team.
    team_reports = {}
    for name in sorted(participants):
        kickoff = _kickoff_for_lol_team(session, name)
        team_reports[name] = _mark_last_n_series(session, name, resolution.get(name, [name]), kickoff, now)

    if not map_stats.get("rate_limited"):
        state.next_retry_at = None
    provider_state.record(
        session, "leaguepedia", "success",
        request_count=requests + map_stats.get("games_queried", 0),
        records_processed=series_new + map_stats.get("maps_new", 0),
        coverage={
            "series_new": series_new,
            "maps_new": map_stats.get("maps_new", 0),
            "team_map_rows_new": map_stats.get("team_rows_new", 0),
            "player_map_rows_new": map_stats.get("players_new", 0),
            "teams": {k: v["eligible"] for k, v in team_reports.items()},
        },
    )
    log("info", f"leaguepedia series_new={series_new} maps_new={map_stats.get('maps_new')} "
                f"players_new={map_stats.get('players_new')} teams={ {k: v['eligible'] for k, v in team_reports.items()} }")
    return {"status": "success", "series": series_new, "maps": map_stats, "teams": team_reports}


# --------------------------------------------------------------------------
# Orchestrator
# --------------------------------------------------------------------------

def run(session: Session) -> dict:
    """One bounded, idempotent ingestion pass restricted to active participants."""
    # Ignore orphaned historical run markers left by a crashed process. A
    # genuinely concurrent ingestion remains protected during its bounded
    # four-hour execution window.
    active_since = datetime.now(UTC) - timedelta(hours=4)
    active = session.exec(
        select(SourceRun).where(
            SourceRun.status.in_(("running", "pending")),
            SourceRun.started_at >= active_since,
        )
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
    freshness = _football_freshness(session, participants["football"], flog)
    football_status = "partial" if api.get("status") in ("partial", "unconfigured") else "success"
    source_runs.finalize(
        session, football_run, football_status,
        message=f"api_football={api.get('status')}; tsdb_evidence={tsdb.get('evidence_rows')}; freshness={ {k: v['eligible_last_10'] for k, v in freshness.items()} }",
        inserted=tsdb.get("evidence_rows", 0) + api.get("fixtures", 0),
    )

    lol_run = source_runs.create_run(session, "lol", "historical_ingestion", "scheduled")

    def llog(level, msg):
        source_runs.log(session, lol_run, level, msg)

    lp = _ingest_leaguepedia(session, lol_run, participants["lol"], llog)
    lol_status = "success" if lp.get("status") in ("success", "gated") else "partial"
    source_runs.finalize(
        session, lol_run, lol_status,
        message=f"leaguepedia={lp.get('status')}; series_new={lp.get('series')}; maps={ (lp.get('maps') or {}).get('maps_new') }",
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
        "football_freshness": freshness,
        "leaguepedia": lp.get("status"),
        "leaguepedia_series": lp.get("series", 0),
        "leaguepedia_maps": lp.get("maps", {}),
        "leaguepedia_teams": lp.get("teams", {}),
        "at": datetime.now(UTC).isoformat(),
    }
