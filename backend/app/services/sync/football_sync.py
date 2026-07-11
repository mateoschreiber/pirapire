"""Manual football synchronization (football-data.org primary, OpenLigaDB fallback).

Now with request pacing (delay between calls) and one retry on HTTP 429 with
Retry-After, so the free tier limit is not exceeded.
"""

from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from ...config import settings
from ...models_football import (
    FootballCompetition,
    FootballMatch,
    FootballPlayer,
    FootballStanding,
    FootballTeam,
)
from ...models_sources import SourceRun
from ...sources.football.football_data_org import FootballDataOrgClient
from ...sources.football.openligadb import OpenLigaDBClient
from .. import provider_state, raw_snapshots, source_runs
from ..secret_provider import SecretProvider
from . import thesportsdb_sync


def _window() -> tuple[str, str]:
    today = datetime.now(UTC).date()
    date_from = today - timedelta(days=settings.sync_default_lookback_days)
    date_to = today + timedelta(days=settings.sync_default_lookahead_days)
    return date_from.isoformat(), date_to.isoformat()


def _upsert_team(session, team_raw, source_name, rank, fallback):
    ext = team_raw.get("id")
    if ext is None:
        return None
    ext = str(ext)
    existing = session.exec(
        select(FootballTeam).where(
            FootballTeam.source_name == source_name,
            FootballTeam.source_external_id == ext,
        )
    ).first()
    if existing is not None:
        if rank >= (existing.source_rank or 0):
            if not existing.short_name and team_raw.get("shortName"):
                existing.short_name = team_raw["shortName"]
            if not existing.tla and team_raw.get("tla"):
                existing.tla = team_raw["tla"]
            if not existing.crest_url and team_raw.get("crest"):
                existing.crest_url = team_raw["crest"]
            if not existing.country and team_raw.get("country"):
                existing.country = team_raw["country"]
            existing.retrieved_at = datetime.now(UTC)
            session.add(existing)
            session.commit()
        return existing.id
    team = FootballTeam(
        source_name=source_name,
        source_external_id=ext,
        name=team_raw.get("name") or "?",
        short_name=team_raw.get("shortName"),
        tla=team_raw.get("tla"),
        crest_url=team_raw.get("crest"),
        country=team_raw.get("country"),
        source_rank=rank,
        fallback_used=fallback,
    )
    session.add(team)
    session.commit()
    session.refresh(team)
    return team.id


def _upsert_competition(session, ncomp, source_name, rank, fallback):
    ext = ncomp.get("source_external_id")
    if ext is None:
        return None
    existing = session.exec(
        select(FootballCompetition).where(
            FootballCompetition.source_name == source_name,
            FootballCompetition.source_external_id == ext,
        )
    ).first()
    if existing is not None:
        return existing.id
    comp = FootballCompetition(
        source_name=source_name,
        source_external_id=ext,
        code=ncomp.get("code"),
        name=ncomp.get("name") or "?",
        country=ncomp.get("country"),
        emblem_url=ncomp.get("emblem_url"),
        source_rank=rank,
        fallback_used=fallback,
    )
    session.add(comp)
    session.commit()
    session.refresh(comp)
    return comp.id


def _apply_match(match, nm, comp_id, home_id, away_id, rank, fallback):
    match.competition_id = comp_id
    match.home_team_id = home_id
    match.away_team_id = away_id
    match.start_time = nm.get("start_time")
    match.status = nm.get("status")
    match.matchday = nm.get("matchday")
    match.stage = nm.get("stage")
    match.group_name = nm.get("group_name")
    match.home_score = nm.get("home_score")
    match.away_score = nm.get("away_score")
    match.ht_home_score = nm.get("ht_home_score")
    match.ht_away_score = nm.get("ht_away_score")
    match.winner = nm.get("winner")
    match.source_rank = rank
    match.fallback_used = fallback
    match.retrieved_at = datetime.now(UTC)


def _upsert_match(session, nm, comp_id, source_name, rank, fallback):
    home_id = _upsert_team(
        session, nm.get("home_team") or {}, source_name, rank, fallback
    )
    away_id = _upsert_team(
        session, nm.get("away_team") or {}, source_name, rank, fallback
    )
    ext = nm["source_external_id"]
    existing = session.exec(
        select(FootballMatch).where(
            FootballMatch.source_external_id == ext,
        )
    ).first()
    if existing is not None:
        if rank < (existing.source_rank or 0):
            return (0, 0, 1)
        _apply_match(existing, nm, comp_id, home_id, away_id, rank, fallback)
        session.add(existing)
        session.commit()
        return (0, 1, 0)
    match = FootballMatch(source_name=source_name, source_external_id=ext)
    _apply_match(match, nm, comp_id, home_id, away_id, rank, fallback)
    session.add(match)
    session.commit()
    return (1, 0, 0)


def _upsert_standing(session, row, comp_id, source_name, rank, fallback):
    team_id = _upsert_team(session, row.get("team") or {}, source_name, rank, fallback)
    existing = session.exec(
        select(FootballStanding).where(
            FootballStanding.source_name == source_name,
            FootballStanding.competition_id == comp_id,
            FootballStanding.team_id == team_id,
            FootballStanding.season == row.get("season"),
        )
    ).first()
    target = existing or FootballStanding(
        source_name=source_name,
        competition_id=comp_id,
        team_id=team_id,
        season=row.get("season"),
    )
    target.position = row.get("position")
    target.played_games = row.get("played_games")
    target.won = row.get("won")
    target.draw = row.get("draw")
    target.lost = row.get("lost")
    target.points = row.get("points")
    target.goals_for = row.get("goals_for")
    target.goals_against = row.get("goals_against")
    target.goal_difference = row.get("goal_difference")
    target.source_rank = rank
    target.fallback_used = fallback
    target.retrieved_at = datetime.now(UTC)
    session.add(target)
    session.commit()
    return (0, 1, 0) if existing else (1, 0, 0)


def _upsert_player(session, raw, team_id, team_name):
    external_id = raw.get("id")
    if external_id is None:
        return (0, 0, 1)
    source_key = f"football-data|player|{external_id}"
    row = session.exec(
        select(FootballPlayer).where(FootballPlayer.source_key == source_key)
    ).first()
    is_new = row is None
    row = row or FootballPlayer(
        source_name="football_data_org",
        source_id=str(external_id),
        name=raw.get("name") or "?",
        source_key=source_key,
    )
    row.name = raw.get("name") or row.name
    row.position = raw.get("position") or row.position
    row.shirt_number = raw.get("shirtNumber")
    row.date_of_birth = raw.get("dateOfBirth") or row.date_of_birth
    row.nationality = raw.get("nationality") or row.nationality
    row.team_id = team_id
    row.team_name = team_name
    row.updated_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    return (1, 0, 0) if is_new else (0, 1, 0)


def _run_wc_teams_and_squads(session, run, client):
    response = client.get_competition_teams("WC")
    if not response.get("ok") or not isinstance(response.get("data"), dict):
        source_runs.log(
            session,
            run,
            "warning",
            f"[WC] teams/squads unavailable status={response.get('status')}",
        )
        return (0, 0, 1)
    data = response["data"]
    raw_snapshots.save_snapshot(
        session,
        run.id,
        client.slug,
        "football",
        "world_cup_teams_squads",
        data,
        external_id="WC",
    )
    inserted = updated = skipped = 0
    for raw_team in data.get("teams") or []:
        normalized = client.normalize_team(raw_team)
        team_id = _upsert_team(
            session, normalized, client.slug, client.rank, False
        )
        if team_id is None:
            skipped += 1
            continue
        for player in raw_team.get("squad") or []:
            i, u, s = _upsert_player(
                session, player, team_id, normalized.get("name") or "?"
            )
            inserted += i
            updated += u
            skipped += s
    source_runs.log(
        session,
        run,
        "info",
        f"[WC] teams={len(data.get('teams') or [])} players_inserted={inserted} "
        f"players_updated={updated}",
    )
    return inserted, updated, skipped


def _run_football_data_org(
    session, run: SourceRun, api_key: str
) -> tuple[int, int, int, bool]:
    inserted = updated = skipped = 0
    any_ok = False

    def log_cb(level, msg):
        source_runs.log(session, run, level, msg)

    client = FootballDataOrgClient(
        api_key=api_key,
        base_url=settings.football_data_base_url,
        request_delay=settings.football_data_request_delay_seconds,
        respect_retry_after=settings.football_data_respect_retry_after,
        cache_ttl_seconds=settings.football_data_cache_ttl_seconds,
        log_callback=log_cb,
    )
    date_from, date_to = _window()

    competitions = settings.competitions_list
    max_comp = int(settings.football_data_max_competitions_per_run)
    if max_comp > 0 and len(competitions) > max_comp:
        log_cb(
            "info",
            f"limiting competitions to {max_comp} of {len(competitions)}: {competitions[:max_comp]}",
        )
        competitions = competitions[:max_comp]

    log_cb(
        "info", f"football-data.org window {date_from}..{date_to} comps={competitions}"
    )

    for code in competitions:
        resp = client.get_competition_matches(code, date_from, date_to)
        if not resp["ok"]:
            log_cb("error", f"[{code}] matches: {resp['error']}")
            continue
        data = resp["data"] or {}
        _, is_new = raw_snapshots.save_snapshot(
            session, run.id, client.slug, "football", "matches", data, external_id=code
        )
        any_ok = True
        if not is_new:
            log_cb("info", f"[{code}] matches unchanged (dedup)")
            skipped += 1
            continue
        comp_raw = data.get("competition") or {}
        comp_id = None
        if comp_raw:
            comp_id = _upsert_competition(
                session,
                client.normalize_competition(comp_raw),
                client.slug,
                client.rank,
                False,
            )
        match_count = len(data.get("matches", []))
        for m in data.get("matches", []):
            i, u, s = _upsert_match(
                session,
                client.normalize_match(m),
                comp_id,
                client.slug,
                client.rank,
                False,
            )
            inserted += i
            updated += u
            skipped += s
        log_cb("info", f"[{code}] {match_count} matches processed")

        # Only fetch standings when matches returned something.
        if match_count > 0:
            st = client.get_competition_standings(code)
            if st["ok"] and st["data"]:
                raw_snapshots.save_snapshot(
                    session,
                    run.id,
                    client.slug,
                    "football",
                    "standings",
                    st["data"],
                    external_id=code,
                )
                for row in client.normalize_standings(st["data"]):
                    i, u, s = _upsert_standing(
                        session, row, comp_id, client.slug, client.rank, False
                    )
                    inserted += i
                    updated += u
                    skipped += s
            elif not st["ok"]:
                log_cb("warning", f"[{code}] standings: {st['error']}")
        else:
            log_cb("info", f"[{code}] no matches in window; skipping standings")

    if settings.football_data_sync_wc_squads:
        i, u, s = _run_wc_teams_and_squads(session, run, client)
        inserted += i
        updated += u
        skipped += s
    log_cb(
        "info",
        f"football-data.org requests={client.request_count} inserted={inserted} "
        f"updated={updated} skipped={skipped}",
    )
    provider_state.record(
        session,
        "football_data_org",
        "success" if any_ok else "error",
        error_code=None if any_ok else "provider_unavailable",
        request_count=client.request_count,
        records_processed=inserted + updated + skipped,
        coverage={"competitions": len(competitions)},
    )
    return inserted, updated, skipped, any_ok


def _run_openligadb(session, run: SourceRun) -> tuple[int, int, int]:
    inserted = updated = skipped = 0
    shortcut = settings.openligadb_league_shortcut
    season = settings.openligadb_season
    if not (shortcut and season):
        source_runs.log(
            session,
            run,
            "warning",
            "OpenLigaDB fallback not configured (set OPENLIGADB_LEAGUE_SHORTCUT / OPENLIGADB_SEASON)",
        )
        return inserted, updated, skipped
    client = OpenLigaDBClient(settings.openligadb_base_url)
    resp = client.get_matches_by_league_season(shortcut, season)
    if not resp["ok"] or not resp["data"]:
        source_runs.log(
            session, run, "error", f"openligadb fallback: {resp.get('error')}"
        )
        return inserted, updated, skipped
    raw_snapshots.save_snapshot(
        session,
        run.id,
        client.slug,
        "football",
        "matches",
        resp["data"],
        external_id=f"{shortcut}/{season}",
    )
    source_runs.log(
        session,
        run,
        "info",
        f"openligadb fallback {shortcut}/{season}: {len(resp['data'])} matches",
    )
    for m in resp["data"]:
        i, u, s = _upsert_match(
            session, client.normalize_match(m), None, client.slug, client.rank, True
        )
        inserted += i
        updated += u
        skipped += s
    return inserted, updated, skipped


def sync(session: Session, run: SourceRun, only_slug: str | None = None) -> dict:
    inserted = updated = skipped = 0
    primary_ok = False

    api_key, secret_source = SecretProvider.get_secret(
        "football_data_org", "api_key", session=session, mark_used=True
    )
    use_primary = only_slug in (None, "football_data_org") and bool(api_key)
    if only_slug in (None, "football_data_org") and not api_key:
        source_runs.log(
            session,
            run,
            "warning",
            "FOOTBALL_DATA_API_KEY not set; using fallback if configured",
        )

    if use_primary:
        i, u, s, primary_ok = _run_football_data_org(session, run, api_key)
        inserted += i
        updated += u
        skipped += s

    need_fallback = only_slug == "openligadb" or (only_slug is None and not primary_ok)
    if need_fallback:
        i, u, s = _run_openligadb(session, run)
        inserted += i
        updated += u
        skipped += s

    if only_slug is None:
        metadata = thesportsdb_sync.sync(session, run)
        inserted += metadata["inserted"]
        updated += metadata["updated"]
        skipped += metadata["skipped"]

    status = source_runs.resolve_status(
        inserted, updated, skipped, run.error_count or 0
    )
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "status": status,
    }
