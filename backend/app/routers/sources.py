from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from ..database import engine, get_session
from ..models_sources import DataSource, SourceCapability, SourceRun
from ..services import source_runs
from ..services import source_registry as registry
from ..services import source_resolver
from ..services.sync import football_sync, lol_sync, riot_sync, sync_all, thesportsdb_sync

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("")
def list_sources() -> list:
    return [registry.as_dict(s) for s in registry.all_sources()]


@router.get("/capabilities")
def list_capabilities() -> list:
    rows = []
    for src in registry.all_sources():
        for data_type in src["use_for"]:
            primary = source_resolver.pick_primary(src["sport"], data_type)
            rows.append(
                {
                    "sport": src["sport"],
                    "data_type": data_type,
                    "source_slug": src["slug"],
                    "rank": src["rank"],
                    "enabled": registry.is_enabled(src),
                    "is_primary": bool(primary and primary["slug"] == src["slug"]),
                    "supports_live": src["supports_live"],
                    "supports_history": src["supports_history"],
                    "supports_manual_import": src["supports_manual_import"],
                }
            )
    return rows


@router.get("/rankings")
def rankings() -> dict:
    def pack(sport: str) -> list:
        ordered = sorted(
            registry.sources_for(sport), key=lambda s: s["rank"], reverse=True
        )
        return [registry.as_dict(s) for s in ordered]

    return {"football": pack("football"), "lol": pack("lol")}


@router.post("/seed")
def seed_sources(session: Session = Depends(get_session)) -> dict:
    now = datetime.now(UTC)
    sources_upserted = 0
    capabilities_upserted = 0

    for src in registry.all_sources():
        enabled = registry.is_enabled(src)
        existing = session.exec(
            select(DataSource).where(DataSource.slug == src["slug"])
        ).first()

        if existing is not None:
            existing.name = src["name"]
            existing.sport = src["sport"]
            existing.rank = src["rank"]
            existing.enabled = enabled
            existing.requires_env = src["requires_env"]
            existing.base_url = src["base_url"]
            existing.description = src["description"]
            existing.reliability_notes = src["reliability_notes"]
            existing.updated_at = now
            session.add(existing)
            data_source = existing
        else:
            data_source = DataSource(
                name=src["name"],
                slug=src["slug"],
                sport=src["sport"],
                rank=src["rank"],
                enabled=enabled,
                requires_env=src["requires_env"],
                base_url=src["base_url"],
                description=src["description"],
                reliability_notes=src["reliability_notes"],
                created_at=now,
                updated_at=now,
            )
            session.add(data_source)

        session.commit()
        session.refresh(data_source)
        sources_upserted += 1

        old_caps = session.exec(
            select(SourceCapability).where(
                SourceCapability.source_id == data_source.id
            )
        ).all()
        for cap in old_caps:
            session.delete(cap)
        session.commit()

        for data_type in src["use_for"]:
            primary = source_resolver.pick_primary(src["sport"], data_type)
            session.add(
                SourceCapability(
                    source_id=data_source.id,
                    sport=src["sport"],
                    data_type=data_type,
                    priority=src["rank"],
                    enabled=enabled,
                    is_primary=bool(primary and primary["slug"] == src["slug"]),
                    supports_live=src["supports_live"],
                    supports_history=src["supports_history"],
                    supports_manual_import=src["supports_manual_import"],
                    notes=src["reliability_notes"],
                )
            )
            capabilities_upserted += 1
        session.commit()

    return {
        "status": "ok",
        "sources_upserted": sources_upserted,
        "capabilities_upserted": capabilities_upserted,
    }


# --- Manual sync (only triggered by these POST endpoints) ---


def _run_sync(run_id: int, kind: str, only_slug: str | None = None) -> None:
    with Session(engine) as session:
        run = session.get(SourceRun, run_id)
        if run is None:
            return
        try:
            if kind == "football":
                result = football_sync.sync(session, run, only_slug)
            elif kind == "lol":
                result = lol_sync.sync(session, run, only_slug)
            elif kind == "thesportsdb":
                result = thesportsdb_sync.sync(session, run)
            elif kind == "riot":
                result = riot_sync.sync(session, run)
            else:
                result = sync_all.sync(session, run)
            source_runs.finalize(
                session,
                run,
                result["status"],
                inserted=result["inserted"],
                updated=result["updated"],
                skipped=result["skipped"],
            )
        except Exception as exc:  # never leave the run hanging
            source_runs.finalize(
                session, run, "error", message=f"unhandled: {type(exc).__name__}: {exc}"
            )


def _start(session, background, sport, kind, only_slug=None) -> dict:
    run = source_runs.create_run(session, sport=sport, source_slug=only_slug)
    background.add_task(_run_sync, run.id, kind, only_slug)
    return {"run_id": run.id, "status": run.status, "sport": sport, "source_slug": only_slug}


@router.post("/sync/football")
def sync_football(background: BackgroundTasks, session: Session = Depends(get_session)) -> dict:
    return _start(session, background, "football", "football")


@router.post("/sync/lol")
def sync_lol(background: BackgroundTasks, session: Session = Depends(get_session)) -> dict:
    return _start(session, background, "lol", "lol")


@router.post("/sync/all")
def sync_all_endpoint(background: BackgroundTasks, session: Session = Depends(get_session)) -> dict:
    return _start(session, background, "all", "all")


_SLUG_KIND = {
    "football_data_org": ("football", "football"),
    "openligadb": ("football", "football"),
    "riot_datadragon": ("lol", "lol"),
    "leaguepedia": ("lol", "lol"),
    "thesportsdb": ("football", "thesportsdb"),
    "riot_api": ("lol", "riot"),
}


@router.post("/sync/{source_slug}")
def sync_by_slug(
    source_slug: str,
    background: BackgroundTasks,
    session: Session = Depends(get_session),
) -> dict:
    if source_slug not in _SLUG_KIND:
        raise HTTPException(status_code=404, detail=f"Unknown or non-syncable source: {source_slug}")
    sport, kind = _SLUG_KIND[source_slug]
    return _start(session, background, sport, kind, only_slug=source_slug)
