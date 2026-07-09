"""Manual LoL synchronization (Riot Data Dragon static data)."""

from datetime import UTC, datetime

from sqlmodel import Session, select

from ...config import settings
from ...models_lol import LolChampion, LolPatch
from ...models_sources import SourceRun
from ...sources.lol.datadragon import RiotDataDragonClient
from .. import raw_snapshots, source_runs


def _upsert_patch(session, version, source_name, rank):
    existing = session.exec(
        select(LolPatch).where(
            LolPatch.source_name == source_name, LolPatch.version == version
        )
    ).first()
    if existing is not None:
        return (0, 0, 1)
    session.add(
        LolPatch(source_name=source_name, version=version, source_rank=rank, fallback_used=False)
    )
    session.commit()
    return (1, 0, 0)


def _upsert_champion(session, champ, source_name, rank, fallback):
    existing = session.exec(
        select(LolChampion).where(
            LolChampion.source_name == source_name,
            LolChampion.champion_id == champ["champion_id"],
        )
    ).first()
    if existing is not None:
        existing.champion_key = champ.get("champion_key")
        existing.name = champ.get("name") or existing.name
        existing.title = champ.get("title")
        existing.version = champ.get("version")
        existing.source_rank = rank
        existing.fallback_used = fallback
        existing.retrieved_at = datetime.now(UTC)
        session.add(existing)
        session.commit()
        return (0, 1, 0)
    session.add(
        LolChampion(
            source_name=source_name,
            champion_id=champ["champion_id"],
            champion_key=champ.get("champion_key"),
            name=champ.get("name") or champ["champion_id"],
            title=champ.get("title"),
            version=champ.get("version"),
            source_rank=rank,
            fallback_used=fallback,
        )
    )
    session.commit()
    return (1, 0, 0)


def sync(session: Session, run: SourceRun, only_slug: str | None = None) -> dict:
    inserted = updated = skipped = 0
    client = RiotDataDragonClient(settings.datadragon_base_url, settings.datadragon_locale)

    versions_resp = client.get_versions()
    if not versions_resp["ok"] or not versions_resp["data"]:
        source_runs.log(session, run, "error", f"versions.json: {versions_resp.get('error')}")
        return {"inserted": 0, "updated": 0, "skipped": 0, "status": "error"}

    versions = versions_resp["data"]
    raw_snapshots.save_snapshot(
        session, run.id, client.slug, "lol", "versions", versions, external_id="versions"
    )
    latest = client.latest_version(versions)
    source_runs.log(session, run, "info", f"latest Data Dragon version: {latest}")
    i, u, s = _upsert_patch(session, latest, client.slug, client.rank)
    inserted += i
    updated += u
    skipped += s

    used_locale = settings.datadragon_locale
    fallback_locale = False
    champ_resp = client.get_champions(latest, used_locale)
    if not champ_resp["ok"] or not champ_resp["data"]:
        source_runs.log(
            session, run, "warning", f"champion.json {used_locale} failed; retrying en_US"
        )
        used_locale = "en_US"
        fallback_locale = True
        champ_resp = client.get_champions(latest, used_locale)

    if champ_resp["ok"] and champ_resp["data"]:
        raw_snapshots.save_snapshot(
            session, run.id, client.slug, "lol", "champion", champ_resp["data"],
            external_id=f"champion-{used_locale}",
        )
        champions = client.normalize_champions(champ_resp["data"], latest)
        for champ in champions:
            i, u, s = _upsert_champion(session, champ, client.slug, client.rank, fallback_locale)
            inserted += i
            updated += u
            skipped += s
        source_runs.log(session, run, "info", f"{len(champions)} champions ({used_locale})")
    else:
        source_runs.log(session, run, "error", "champion.json failed on both locales")

    status = source_runs.resolve_status(inserted, updated, skipped, run.error_count or 0)
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "status": status}
