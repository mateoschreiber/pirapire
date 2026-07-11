"""Riot enrichment limited to confirmed identities and personal match references."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlmodel import Session, select

from ...config import settings
from ...models_lol import RiotMatchReference, RiotPlayerIdentity
from ...models_sources import IntegrationCredential, SourceRun
from ...sources.lol.riot_api import RiotAPIClient
from .. import provider_state, raw_snapshots, source_runs
from ..secret_provider import SecretProvider


def _credential_metadata(session: Session) -> tuple[str, str]:
    row = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.provider_slug == "riot_api",
            IntegrationCredential.credential_name == "api_key",
        )
    ).first()
    if not row:
        return settings.riot_default_platform, settings.riot_default_region
    routes = json.loads(row.regional_routes) if row.regional_routes else []
    return (
        row.default_platform or settings.riot_default_platform,
        routes[0] if routes else settings.riot_default_region,
    )


def _match_started_at(info: dict) -> datetime | None:
    value = info.get("gameStartTimestamp")
    if not value:
        return None
    return datetime.fromtimestamp(int(value) / 1000, tz=UTC)


def sync(session: Session, run: SourceRun) -> dict:
    api_key, source = SecretProvider.get_secret(
        "riot_api", "api_key", session=session, mark_used=True
    )
    if not api_key:
        row = session.exec(
            select(IntegrationCredential).where(
                IntegrationCredential.provider_slug == "riot_api",
                IntegrationCredential.credential_name == "api_key",
            )
        ).first()
        provider_state.record(
            session,
            "riot_api",
            "expired" if row and row.test_status == "expired" else "unconfigured",
            error_code="expired_key" if row and row.test_status == "expired" else None,
        )
        source_runs.log(
            session,
            run,
            "info",
            "Riot API not configured or expired; complementary sync skipped",
        )
        return {"inserted": 0, "updated": 0, "skipped": 1, "status": "success"}
    platform, region = _credential_metadata(session)

    def log_cb(level, message):
        source_runs.log(session, run, level, message)

    client = RiotAPIClient(
        api_key,
        platform=platform,
        region=region,
        request_delay=settings.riot_request_delay_seconds,
        cache_ttl_seconds=settings.riot_cache_ttl_seconds,
        log_callback=log_cb,
    )
    status_result = client.get_platform_status()
    if not status_result.get("ok"):
        status = status_result.get("status")
        if status == 401:
            error_code = "invalid_key"
        elif status == 403:
            error_code = "forbidden"
        elif status == 429:
            error_code = "quota_exceeded"
        elif status_result.get("error") == "timeout":
            error_code = "timeout"
        else:
            error_code = "provider_unavailable"
        credential = session.exec(
            select(IntegrationCredential).where(
                IntegrationCredential.provider_slug == "riot_api",
                IntegrationCredential.credential_name == "api_key",
            )
        ).first()
        if credential:
            credential.last_error_code = error_code
            if status in (401, 403):
                credential.test_status = "failed"
            session.add(credential)
            session.commit()
        provider_state.record(
            session,
            "riot_api",
            "error",
            error_code=error_code,
            request_count=client.request_count,
        )
        log_cb("warning", f"Riot complementary sync skipped error={error_code}")
        return {"inserted": 0, "updated": 0, "skipped": 1, "status": "success"}
    identities = session.exec(
        select(RiotPlayerIdentity)
        .where(RiotPlayerIdentity.confirmed.is_(True))
        .order_by(RiotPlayerIdentity.valid_from.desc())
        .limit(settings.riot_max_identities_per_run)
    ).all()
    inserted = updated = skipped = 0
    for identity in identities:
        if not identity.puuid:
            account = client.account_by_riot_id(identity.game_name, identity.tag_line)
            if not account.get("ok") or not isinstance(account.get("data"), dict):
                skipped += 1
                continue
            identity.puuid = account["data"].get("puuid")
            if not identity.puuid:
                skipped += 1
                continue
            identity.last_verified_at = datetime.now(UTC)
            session.add(identity)
            session.commit()
            updated += 1
        ids_result = client.match_ids_by_puuid(
            identity.puuid, settings.riot_matches_per_identity
        )
        if not ids_result.get("ok") or not isinstance(ids_result.get("data"), list):
            skipped += 1
            continue
        for match_id in ids_result["data"]:
            if session.exec(
                select(RiotMatchReference).where(
                    RiotMatchReference.match_id == str(match_id)
                )
            ).first():
                skipped += 1
                continue
            detail = client.match_by_id(str(match_id))
            if not detail.get("ok") or not isinstance(detail.get("data"), dict):
                skipped += 1
                continue
            raw_snapshots.save_snapshot(
                session,
                run.id,
                client.slug,
                "lol",
                "personal_verified_match",
                detail["data"],
                external_id=str(match_id),
            )
            info = detail["data"].get("info") or {}
            session.add(
                RiotMatchReference(
                    identity_id=identity.id,
                    match_id=str(match_id),
                    queue_id=info.get("queueId"),
                    game_type=info.get("gameType"),
                    game_mode=info.get("gameMode"),
                    game_started_at=_match_started_at(info),
                )
            )
            session.commit()
            inserted += 1
    log_cb(
        "info",
        f"Riot complementary source={source} identities={len(identities)} "
        f"requests={client.request_count} matches={inserted} skipped={skipped} "
        "scope=personal_verified",
    )
    provider_state.record(
        session,
        "riot_api",
        "success",
        request_count=client.request_count,
        records_processed=inserted + updated + skipped,
        coverage={"confirmed_identities": len(identities), "personal_matches": inserted},
    )
    return {
        "inserted": inserted,
        "updated": updated,
        "skipped": skipped,
        "status": "success",
    }
