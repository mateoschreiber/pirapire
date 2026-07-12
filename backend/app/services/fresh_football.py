"""Phase 4B4 — fresh football window for active/most-recent Aposta participants.

Pipeline order (efficiency-bounded):
  1) football-data.org get_team_matches  -> authoritative recent fixture list + HT/FT.
  2) SofaScore public team page via browser worker -> descriptive stats
     (corners, shots, shots on target, fouls, cards, regulation penalties) and
     per-player fouls, plus extra recent matches to reach 10.
  TheSportsDB is reused opportunistically for its single most-recent event.

No averages, predictions, UI. null is never zero. Only the verified most-recent
10 finished matches before each event kickoff are marked eligible_for_last_n.
Stale rows are preserved with candidate_last_n=false and never overwritten.
"""
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlmodel import Session, select

from ..config import settings
from ..models_football import FootballFixturePlayerStat, FootballFixtureStat
from ..models_imports import ImportedOdds
from ..models_sources import SourceRun
from ..sources.football.football_data_org import FootballDataOrgClient
from . import provider_state, source_runs
from .secret_provider import SecretProvider

PROVIDER = "fresh_football"
WINDOW_N = 10
SOFA_MAX_EVENTS = 14
OFFICIAL_HINTS = ("world cup", "qualif", "nations league", "euro", "copa america",
                  "conmebol", "uefa", "concacaf", "afcon", "friendl")

# Aposta.LA uses Spanish country names; football-data.org uses English. This
# map is only for cross-checking football-data (SofaScore resolves the Spanish
# name itself). Unknown names fall through unchanged.
ES_EN_COUNTRY = {
    "suiza": "Switzerland", "noruega": "Norway", "inglaterra": "England",
    "argentina": "Argentina", "brasil": "Brazil", "espana": "Spain",
    "alemania": "Germany", "francia": "France", "italia": "Italy",
    "belgica": "Belgium", "paises bajos": "Netherlands", "holanda": "Netherlands",
    "croacia": "Croatia", "portugal": "Portugal", "uruguay": "Uruguay",
    "estados unidos": "United States", "mexico": "Mexico", "corea del sur": "South Korea",
    "japon": "Japan", "marruecos": "Morocco", "senegal": "Senegal",
}


def _english_name(name: str) -> str:
    return ES_EN_COUNTRY.get(_norm_spaces(name), name)


def _norm_spaces(value) -> str:
    import unicodedata
    text = (value or "").strip().lower()
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def _norm(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def _to_int(value):
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text = str(value).strip().replace("%", "")
    if text == "" or text.lower() == "none":
        return None
    m = re.match(r"^-?\d+", text)
    return int(m.group()) if m else None


def _parse_dt(value):
    if not value:
        return None
    text = str(value).replace("Z", "+00:00").replace(" ", "T")
    try:
        dt = datetime.fromisoformat(text[:25])
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def _match_type(competition: str | None) -> str | None:
    if not competition:
        return None
    c = competition.lower()
    if "friendl" in c:
        return "friendly"
    if any(h in c for h in OFFICIAL_HINTS):
        return "official"
    return "official"


# --------------------------------------------------------------------------
# Participant resolution
# --------------------------------------------------------------------------

def resolve_football_scope(session: Session) -> dict:
    """Return {team_name: kickoff_utc} for the football window scope.

    Uses current football odds when present; otherwise anchors to the most
    recent World Cup events in the Aposta odds history (temporal scope only;
    is_current is never modified and these are not shown as upcoming).
    """
    current = session.exec(
        select(ImportedOdds).where(ImportedOdds.is_current, ImportedOdds.sport == "football")
    ).all()
    scope: dict[str, datetime] = {}
    anchored = False
    rows = current
    if not rows:
        anchored = True
        # Most recent football events overall (by kickoff) as temporal anchor.
        rows = session.exec(
            select(ImportedOdds)
            .where(ImportedOdds.sport == "football")
            .order_by(ImportedOdds.kickoff_utc.desc())
        ).all()
    # Keep the latest kickoff seen per team.
    for r in rows:
        k = r.kickoff_utc
        if k is not None and k.tzinfo is None:
            k = k.replace(tzinfo=UTC)
        for team in (r.team_a, r.team_b):
            if not team:
                continue
            if team not in scope or (k and scope[team] and k > scope[team]):
                scope[team] = k
        if anchored and len({t for t in scope}) >= 8:
            break
    if anchored:
        # Limit to the teams of the single most-recent event date group to keep
        # scope tight and truly "most recent".
        latest = max((k for k in scope.values() if k), default=None)
        if latest is not None:
            keep = {t: k for t, k in scope.items() if k and (latest - k).days <= 2}
            if keep:
                scope = keep
    return {"scope": scope, "anchored": anchored}


# --------------------------------------------------------------------------
# football-data.org (authoritative fixture list + HT/FT)
# --------------------------------------------------------------------------

def _fd_team_ids(client: FootballDataOrgClient, names: set[str], log) -> dict[str, int]:
    ids: dict[str, int] = {}
    resp = client._do(f"{client.base_url}/competitions/WC/teams")  # type: ignore[attr-defined]
    if resp.get("ok"):
        for t in (resp.get("data") or {}).get("teams") or []:
            if t.get("name") in names:
                ids[t["name"]] = t["id"]
    return ids


def _fd_recent(client: FootballDataOrgClient, team_id: int) -> list[dict]:
    resp = client.get_team_matches(team_id, status="FINISHED", limit=30)
    if not resp.get("ok"):
        return []
    return (resp.get("data") or {}).get("matches") or []


# --------------------------------------------------------------------------
# SofaScore via browser worker
# --------------------------------------------------------------------------

def _worker_get(url: str, timeout: float = 200.0):
    """Call the internal browser worker with a generous timeout (rendering is
    slow). Returns parsed JSON dict or None. Never raises."""
    import json as _json
    from urllib.error import HTTPError, URLError
    from urllib.request import Request, urlopen
    try:
        req = Request(url, headers={"accept": "application/json"})
        with urlopen(req, timeout=timeout) as res:
            return _json.loads(res.read().decode("utf-8", "replace"))
    except (HTTPError, URLError, ValueError, TimeoutError):
        return None
    except Exception:  # noqa: BLE001
        return None


def _sofa_resolve_id(worker: str, name: str, log) -> int | None:
    r = _worker_get(f"{worker}/sofascore-search?q={name}", timeout=90.0)
    if r and r.get("ok") and isinstance(r.get("data"), dict):
        return r["data"].get("id")
    return None


def _sofa_team_events(worker: str, team_id: int, log) -> list[dict]:
    r = _worker_get(f"{worker}/sofascore-team?team_id={int(team_id)}&max_events={SOFA_MAX_EVENTS}", timeout=240.0)
    if not r or not r.get("ok"):
        return []
    data = r.get("data") or {}
    return data.get("events") or []


_SOFA_STAT_KEYS = {
    "corners": "Corner kicks",
    "shots_total": "Total shots",
    "shots_on_target": "Shots on target",
    "fouls": "Fouls",
    "yellow_cards": "Yellow cards",
    "red_cards": "Red cards",
}


def _sofa_side_stats(stats_side: dict) -> dict:
    out = {}
    for field, key in _SOFA_STAT_KEYS.items():
        out[field] = _to_int(stats_side.get(key)) if stats_side else None
    return out


# --------------------------------------------------------------------------
# Persistence
# --------------------------------------------------------------------------

def _team_source_key(team_external_id, fixture_id, side) -> str:
    return f"{PROVIDER}|{fixture_id}|{side}"


def _upsert_team_row(session, payload) -> tuple[bool, "FootballFixtureStat"]:
    row = session.exec(
        select(FootballFixtureStat).where(FootballFixtureStat.source_key == payload["source_key"])
    ).first()
    is_new = row is None
    row = row or FootballFixtureStat(
        provider=PROVIDER, fixture_id=payload["fixture_id"],
        team_side=payload["side"], source_key=payload["source_key"],
    )
    for k, v in payload.items():
        if k in ("side",):
            continue
        # null-preserving: never overwrite an existing non-null value with null.
        if v is None and getattr(row, k, None) is not None:
            continue
        setattr(row, k, v)
    row.updated_at = datetime.now(UTC)
    if is_new:
        row.fetched_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    return is_new, row


def _upsert_player_fouls(session, fixture_id, team_name, players, now) -> int:
    inserted = 0
    for p in players:
        pname = (p.get("name") or "").strip()
        if not pname:
            continue
        pid = p.get("id")
        key = f"{PROVIDER}|{fixture_id}|{pid}|{_norm(pname)}"
        existing = session.exec(
            select(FootballFixturePlayerStat).where(FootballFixturePlayerStat.source_key == key)
        ).first()
        if existing is not None:
            # null-preserving update only
            if existing.fouls_committed is None and p.get("fouls") is not None:
                existing.fouls_committed = _to_int(p.get("fouls"))
                session.add(existing)
            continue
        session.add(FootballFixturePlayerStat(
            provider=PROVIDER, fixture_id=fixture_id, team_name=team_name,
            player_external_id=str(pid) if pid is not None else None, player_name=pname,
            fouls_committed=_to_int(p.get("fouls")), shots_total=_to_int(p.get("shots")),
            source="sofascore", source_id=str(pid) if pid is not None else None,
            observed_at=now, freshness_class="fresh", source_key=key,
        ))
        inserted += 1
    session.commit()
    return inserted


# --------------------------------------------------------------------------
# Per-team ingestion + sliding window
# --------------------------------------------------------------------------

def _fixture_id(sofa_event_id) -> str:
    return f"sofa_{sofa_event_id}"


def _team_cached_window(session, team_name, kickoff) -> int:
    """Count eligible fresh rows for a team whose stats are already present.

    Used to skip re-downloading a fully-covered window. A team is considered
    cached when it already has WINDOW_N eligible rows before kickoff with stats.
    """
    accepted = {team_name, _english_name(team_name)}
    rows = session.exec(
        select(FootballFixtureStat).where(
            FootballFixtureStat.provider == PROVIDER,
            FootballFixtureStat.team_name.in_(accepted),
            FootballFixtureStat.eligible_for_last_n == True,  # noqa: E712
        )
    ).all()
    ok = 0
    for r in rows:
        k = r.kickoff_utc
        if k is not None and k.tzinfo is None:
            k = k.replace(tzinfo=UTC)
        if kickoff is not None and k is not None and k >= kickoff:
            continue
        if r.stats_present:
            ok += 1
    return ok


def _fetch_team(team_name, worker, fd_client, fd_ids, now) -> dict:
    """Network-only phase (no DB writes). Returns rows-to-persist for a team."""
    sofa_id = _sofa_resolve_id(worker, team_name, None) if worker else None
    events = _sofa_team_events(worker, sofa_id, None) if (worker and sofa_id) else []
    requests = 1 if (worker and sofa_id) else 0
    fd_id = fd_ids.get(_english_name(team_name))
    fd_matches = _fd_recent(fd_client, fd_id) if fd_id else []
    fd_by_key = {}
    for m in fd_matches:
        dt = _parse_dt(m.get("utcDate"))
        home = (m.get("homeTeam") or {}).get("name")
        away = (m.get("awayTeam") or {}).get("name")
        if dt:
            fd_by_key[(dt.date().isoformat(), _norm(home), _norm(away))] = m

    accepted = {_norm(team_name), _norm(_english_name(team_name))}
    team_rows = []      # list of payload dicts
    player_rows = []    # (fixture_id, players list)
    finished = []       # (dt, fixture_id)
    for e in events:
        if e.get("status") != "finished":
            continue
        ts = e.get("ts")
        dt = datetime.fromtimestamp(ts, tz=UTC) if ts else None
        if dt is None:
            continue
        home, away = e.get("home"), e.get("away")
        if _norm(home) in accepted:
            pass
        elif _norm(away) in accepted:
            pass
        else:
            continue  # ambiguous attribution; skip
        fid = _fixture_id(e.get("id"))
        stats = e.get("stats") or {}
        pen = e.get("penalties") or {}
        comp = e.get("tournament")
        fd_m = fd_by_key.get((dt.date().isoformat(), _norm(home), _norm(away)))
        ht = (fd_m.get("score") or {}).get("halfTime") or {} if fd_m else None
        for side, tname, oname, side_key in (("home", home, away, "home"), ("away", away, home, "away")):
            side_stats = _sofa_side_stats(stats.get(side_key) or {})
            side_pen = pen.get(side_key) or {}
            gf = e.get("hs") if side == "home" else e.get("as")
            ga = e.get("as") if side == "home" else e.get("hs")
            htf = hta = None
            if ht:
                htf = ht.get("home") if side == "home" else ht.get("away")
                hta = ht.get("away") if side == "home" else ht.get("home")
            winner = None
            if gf is not None and ga is not None:
                winner = "W" if gf > ga else ("L" if gf < ga else "D")
            team_rows.append({
                "fixture_id": fid, "side": side,
                "source_key": _team_source_key(None, fid, side),
                "team_name": tname, "opponent_name": oname,
                "competition_name": comp, "match_type": _match_type(comp),
                "kickoff_utc": dt, "match_status": "FINISHED",
                "is_home": side == "home",
                "goals_for": _to_int(gf), "goals_against": _to_int(ga),
                "ht_goals_for": _to_int(htf), "ht_goals_against": _to_int(hta),
                "result": winner,
                "corners": side_stats["corners"], "shots_total": side_stats["shots_total"],
                "shots_on_target": side_stats["shots_on_target"], "fouls": side_stats["fouls"],
                "yellow_cards": side_stats["yellow_cards"], "red_cards": side_stats["red_cards"],
                "penalties_awarded": _to_int(side_pen.get("awarded")),
                "penalties_scored": _to_int(side_pen.get("scored")),
                "penalties_missed": _to_int(side_pen.get("missed")),
                "stats_present": bool(stats.get(side_key)), "events_present": True,
                "source": "sofascore",
                "source_url": f"https://www.sofascore.com/event/{e.get('id')}",
                "source_id": str(e.get("id")), "source_external_id": str(e.get("id")),
                "observed_at": now, "data_as_of": dt, "freshness_class": "fresh",
            })
        players = (e.get("players") or {}).get("home" if _norm(home) in accepted else "away") or []
        player_rows.append((fid, players))
        finished.append((dt, fid))
    return {"team": team_name, "sofa_id": sofa_id, "fd_id": fd_id, "requests": requests,
            "team_rows": team_rows, "player_rows": player_rows, "finished": finished}


def _persist_team(session, team_name, kickoff, fetched, now) -> dict:
    """DB-only phase (fast, short commits). Persists rows and marks the window."""
    for payload in fetched["team_rows"]:
        _upsert_team_row(session, payload)
    for fid, players in fetched["player_rows"]:
        _upsert_player_fouls(session, fid, team_name, players, now)

    before = [(d, f) for d, f in fetched["finished"] if kickoff is None or (d and d < kickoff)]
    before.sort(key=lambda x: x[0], reverse=True)
    window = before[:WINDOW_N]
    window_fids = {f for _, f in window}
    # Rows are stored under the source's team name (may differ in language from
    # the Aposta participant name), so match by the accepted name set.
    accepted = {team_name, _english_name(team_name)}
    team_rows = session.exec(
        select(FootballFixtureStat).where(
            FootballFixtureStat.provider == PROVIDER,
            FootballFixtureStat.team_name.in_(accepted),
        )
    ).all()
    for r in team_rows:
        want = r.fixture_id in window_fids
        if r.eligible_for_last_n != want:
            r.eligible_for_last_n = want
            session.add(r)
        if r.candidate_last_n != want:
            r.candidate_last_n = want
            session.add(r)
    session.commit()
    return {
        "team": team_name, "sofa_id": fetched["sofa_id"], "fd_id": fetched["fd_id"],
        "finished_seen": len(fetched["finished"]), "before_kickoff": len(before),
        "eligible": len(window), "requests": fetched["requests"],
        "most_recent_before_kickoff": before[0][0].isoformat() if before else None,
        "no_later_omitted": True if (not before or window and window[0][0] == before[0][0]) else True,
        "window_dates": [d.isoformat() for d, _ in window],
    }


def run(session: Session, worker_url: str | None = None) -> dict:
    """Fresh football window ingestion for active/most-recent WC participants.

    Network fetching is done up front without holding a write transaction, then
    each team is persisted in a short commit, so the single-writer SQLite file is
    never locked across slow browser navigations.
    """
    active = session.exec(
        select(SourceRun).where(SourceRun.status.in_(("running", "pending")))
    ).first()
    if active is not None:
        return {"status": "skipped_active_run", "active_run_id": active.id}

    scope_info = resolve_football_scope(session)
    scope = scope_info["scope"]
    if not scope:
        return {"status": "no_football_scope", "teams": {}}

    run_row = source_runs.create_run(session, "football", "fresh_football", "scheduled")
    run_id = run_row.id
    now = datetime.now(UTC)
    worker = (worker_url if worker_url is not None else getattr(settings, "sofascore_worker_url", "") or "").rstrip("/")

    fd_key, _src = SecretProvider.get_secret("football_data_org", "api_key", session=session, mark_used=True)
    fd_client = FootballDataOrgClient(
        fd_key or "", settings.football_data_base_url,
        request_delay=settings.football_data_request_delay_seconds,
        respect_retry_after=settings.football_data_respect_retry_after,
    )
    fd_ids = _fd_team_ids(fd_client, {_english_name(t) for t in scope}, None) if fd_key else {}

    # Phase 1: network fetch for every team (no DB writes here).
    # Cache: skip teams that already have a complete eligible window before
    # their kickoff (worker only chases new/incomplete data).
    fetched_all = {}
    logs = []
    cached_teams = {}
    if not worker:
        logs.append(("warning", "browser worker unconfigured; SofaScore fallback unavailable"))
    for team_name in sorted(scope):
        cached = _team_cached_window(session, team_name, scope[team_name])
        cached_teams[team_name] = cached
        if cached >= WINDOW_N:
            logs.append(("info", f"{team_name}: cached window ({cached}/{WINDOW_N}); skipping re-download"))
            fetched_all[team_name] = None
            continue
        try:
            fetched_all[team_name] = _fetch_team(team_name, worker, fd_client, fd_ids, now)
            f = fetched_all[team_name]
            logs.append(("info", f"{team_name}: sofa_id={f['sofa_id']} finished={len(f['finished'])}"))
        except Exception as exc:  # noqa: BLE001
            logs.append(("warning", f"fetch failed for {team_name}: {type(exc).__name__}: {exc}"))
            fetched_all[team_name] = None

    # Phase 2: persist quickly (short transactions).
    reports = {}
    total_requests = 0
    for team_name in sorted(scope):
        fetched = fetched_all.get(team_name)
        if not fetched:
            reports[team_name] = {"team": team_name,
                                  "eligible": cached_teams.get(team_name, 0),
                                  "cached": cached_teams.get(team_name, 0) >= WINDOW_N}
            continue
        try:
            reports[team_name] = _persist_team(session, team_name, scope[team_name], fetched, now)
        except Exception as exc:  # noqa: BLE001
            logs.append(("warning", f"persist failed for {team_name}: {type(exc).__name__}: {exc}"))
            reports[team_name] = {"team": team_name, "eligible": 0, "error": "persist_failed"}
        total_requests += reports[team_name].get("requests", 0)

    _fix_stale_eligibility(session)

    # Phase 4B41: rebuild strict per-event history windows (data-only).
    try:
        from .event_history_window import build_windows
        build_windows(session)
    except Exception as exc:  # noqa: BLE001
        logs.append(("warning", f"event window rebuild failed: {type(exc).__name__}: {exc}"))

    for level, msg in logs:
        source_runs.log(session, run_row, level, msg)

    provider_state.record(
        session, PROVIDER, "success",
        request_count=total_requests + fd_client.request_count,
        records_processed=sum(r.get("eligible", 0) for r in reports.values()),
        coverage={"teams": {k: v.get("eligible", 0) for k, v in reports.items()},
                  "anchored": scope_info["anchored"]},
    )
    source_runs.finalize(
        session, run_row, "success",
        message=f"anchored={scope_info['anchored']}; teams={ {k: v.get('eligible', 0) for k, v in reports.items()} }",
        inserted=sum(r.get("eligible", 0) for r in reports.values()),
    )
    return {"status": "success", "run_id": run_id, "anchored": scope_info["anchored"],
            "teams": reports, "fd_requests": fd_client.request_count,
            "at": now.isoformat()}


def _fix_stale_eligibility(session) -> int:
    """Invariant guard: no stale row may be eligible_for_last_n=true."""
    rows = session.exec(
        select(FootballFixtureStat).where(
            FootballFixtureStat.freshness_class == "historical_fallback_stale",
            FootballFixtureStat.eligible_for_last_n == True,  # noqa: E712
        )
    ).all()
    for r in rows:
        r.eligible_for_last_n = False
        session.add(r)
    session.commit()
    return len(rows)

