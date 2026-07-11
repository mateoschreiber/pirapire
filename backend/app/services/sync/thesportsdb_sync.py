"""Conservative TheSportsDB metadata fallback for existing football entities."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from sqlmodel import Session, select

from ...config import settings
from ...models_football import FootballEntityMetadata, FootballTeam
from ...models_sources import SourceRun
from ...sources.football.thesportsdb import TheSportsDBClient
from .. import provider_state, raw_snapshots, source_runs
from ..secret_provider import SecretProvider


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9]", "", (value or "").casefold())


def _unambiguous_team(rows: list[dict], team: FootballTeam) -> dict | None:
    expected = {_norm(team.name), _norm(team.short_name), _norm(team.tla)} - {""}
    matches = []
    for row in rows:
        if (row.get("strSport") or "").casefold() not in {"soccer", "football"}:
            continue
        names = {
            _norm(row.get("strTeam")),
            _norm(row.get("strTeamShort")),
        }
        names.update(_norm(x) for x in (row.get("strAlternate") or "").split(","))
        if expected & (names - {""}):
            matches.append(row)
    return matches[0] if len(matches) == 1 else None


def _save_provenance(session: Session, team: FootballTeam, raw: dict) -> bool:
    external_id = str(raw.get("idTeam") or "")
    if not external_id:
        return False
    row = session.exec(
        select(FootballEntityMetadata).where(
            FootballEntityMetadata.entity_type == "team",
            FootballEntityMetadata.internal_id == team.id,
            FootballEntityMetadata.source_name == "thesportsdb",
            FootballEntityMetadata.source_external_id == external_id,
        )
    ).first()
    is_new = row is None
    row = row or FootballEntityMetadata(
        entity_type="team",
        internal_id=team.id,
        source_name="thesportsdb",
        source_external_id=external_id,
    )
    row.canonical_name = raw.get("strTeam")
    row.aliases_json = json.dumps(
        [x.strip() for x in (raw.get("strAlternate") or "").split(",") if x.strip()]
    )
    row.image_url = raw.get("strBadge") or raw.get("strTeamBadge")
    row.sport = raw.get("strSport")
    row.fallback_used = True
    row.retrieved_at = datetime.now(UTC)
    session.add(row)
    return is_new


def sync(session: Session, run: SourceRun) -> dict:
    api_key, source = SecretProvider.get_secret(
        "thesportsdb", "api_key", session=session, mark_used=True
    )
    if not api_key:
        provider_state.record(session, "thesportsdb", "unconfigured")
        source_runs.log(session, run, "info", "TheSportsDB free-v1 unavailable; skipped")
        return {"inserted": 0, "updated": 0, "skipped": 1, "status": "success"}

    def log_cb(level, message):
        source_runs.log(session, run, level, message)

    client = TheSportsDBClient(
        api_key,
        request_delay=settings.thesportsdb_request_delay_seconds,
        cache_ttl_seconds=settings.thesportsdb_cache_ttl_seconds,
        log_callback=log_cb,
    )
    candidates = session.exec(
        select(FootballTeam)
        .where(FootballTeam.source_name == "football_data_org")
        .order_by(FootballTeam.retrieved_at.desc())
    ).all()
    candidates = [t for t in candidates if not t.crest_url or not t.country]
    candidates = candidates[: max(0, settings.thesportsdb_max_entities_per_run)]
    inserted = updated = skipped = 0
    provider_failed = False
    for team in candidates:
        result = client.search_teams(team.name)
        if not result.get("ok"):
            provider_failed = True
            log_cb("warning", f"TheSportsDB metadata unavailable status={result.get('status')}")
            skipped += 1
            continue
        data = result.get("data") or {}
        raw_snapshots.save_snapshot(
            session,
            run.id,
            client.slug,
            "football",
            "team_metadata",
            data,
            external_id=str(team.id),
        )
        matched = _unambiguous_team(data.get("teams") or [], team)
        if matched is None:
            skipped += 1
            continue
        changed = False
        badge = matched.get("strBadge") or matched.get("strTeamBadge")
        if not team.crest_url and badge:
            team.crest_url = badge
            changed = True
        if not team.country and matched.get("strCountry"):
            team.country = matched["strCountry"]
            changed = True
        if not team.short_name and matched.get("strTeamShort"):
            team.short_name = matched["strTeamShort"]
            changed = True
        if changed:
            session.add(team)
            updated += 1
        if _save_provenance(session, team, matched):
            inserted += 1
        session.commit()
    log_cb(
        "info",
        f"TheSportsDB free-v1 source={source} requests={client.request_count} "
        f"metadata_rows={inserted} teams_enriched={updated} skipped={skipped}",
    )
    provider_state.record(
        session,
        "thesportsdb",
        "error" if provider_failed and not (inserted or updated) else "success",
        error_code="provider_unavailable" if provider_failed else None,
        request_count=client.request_count,
        records_processed=inserted + updated + skipped,
        coverage={"metadata_rows": inserted, "teams_enriched": updated},
    )
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "status": "success",
    }
