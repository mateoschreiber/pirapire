import json
import sys, os, time, logging
from threading import Lock
from datetime import datetime, timezone
from pathlib import Path
from sqlmodel import Session, select

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.config import settings
from app.database import engine, init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [worker] %(message)s")
log = logging.getLogger("worker")

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    log.error("apscheduler not installed. Run: pip install apscheduler")
    sys.exit(1)

scheduler = BackgroundScheduler(timezone="UTC")
oracle_import_lock = Lock()


def _session():
    return Session(engine)


def _oracle_import_active() -> bool:
    from app.models_lol import ImportBatch, SourceRun
    with _session() as session:
        queued_upload = session.exec(select(ImportBatch).where(
            ImportBatch.source_code == "oracles_elixir",
            ImportBatch.status == "running",
        )).first() is not None
        remote_sync = session.exec(select(SourceRun).where(
            SourceRun.source_code == "oracles_elixir",
            SourceRun.job == "remote_sync",
            SourceRun.status == "running",
        )).first() is not None
        return queued_upload or remote_sync


def job_sync_schedule():
    if _oracle_import_active():
        log.info("sync_schedule: skipped while an Oracle import holds the database")
        return
    log.info("sync_schedule: start")
    try:
        from app.services.sync.lol_sync import sync_leaguepedia_schedule
        with _session() as s:
            result = sync_leaguepedia_schedule(s)
        log.info(f"sync_schedule: done {result}")
    except Exception as e:
        log.exception(f"sync_schedule: failed {e}")


def job_sync_datadragon():
    if _oracle_import_active():
        log.info("sync_datadragon: skipped while an Oracle import holds the database")
        return
    log.info("sync_datadragon: start")
    try:
        from app.services.sync.lol_sync import sync_datadragon
        with _session() as s:
            result = sync_datadragon(s)
        log.info(f"sync_datadragon: done {result}")
    except Exception as e:
        log.exception(f"sync_datadragon: failed {e}")


def job_sync_team_logos():
    try:
        from app.services.team_logo_sync import sync_official_team_logos

        result = sync_official_team_logos()
        log.info(f"sync_team_logos: done {result}")
    except Exception as e:
        log.exception(f"sync_team_logos: failed {e}")


def job_import_odds():
    if _oracle_import_active():
        log.info("import_odds: skipped while an Oracle import holds the database")
        return
    log.info("import_odds: start")
    try:
        from app.services.lol_odds_importer import import_odds_directory
        with _session() as s:
            result = import_odds_directory(s)
        log.info(f"import_odds: done {result}")
    except Exception as e:
        log.exception(f"import_odds: failed {e}")


def job_import_oracles():
    if _oracle_import_active() or not oracle_import_lock.acquire(blocking=False):
        log.info("import_oracles: skipped while another Oracle import is active")
        return
    log.info("import_oracles: start")
    try:
        from app.services.imports.oracles_elixir_importer import import_oracles_inbox
        with _session() as s:
            result = import_oracles_inbox(s)
        log.info(f"import_oracles: done {result}")
    except Exception as e:
        log.exception(f"import_oracles: failed {e}")
    finally:
        oracle_import_lock.release()


def job_process_queued_oracle_uploads():
    """Process UI uploads durably from the worker instead of the web process."""
    if _oracle_import_active() or not oracle_import_lock.acquire(blocking=False):
        return
    try:
        from app.models_lol import ImportBatch
        from app.routers.sources import _process_import_batch

        with _session() as session:
            batches = session.exec(select(ImportBatch).where(
                ImportBatch.source_code == "oracles_elixir",
                ImportBatch.status == "queued",
            ).order_by(ImportBatch.created_at)).all()

        uploads = Path(settings.lol_history_import_dir) / "inbox" / "uploads"
        for batch in batches:
            target = uploads / f"{batch.sha256[:12]}-{batch.filename}"
            if not target.is_file():
                log.error("queued Oracle batch %s has no upload file: %s", batch.id, target)
                continue
            with _session() as session:
                replacement = session.exec(select(ImportBatch).where(
                    ImportBatch.source_code == "oracles_elixir",
                    ImportBatch.filename == batch.filename,
                    ImportBatch.id != batch.id,
                    ImportBatch.status == "success",
                )).first() is not None
            log.info("processing queued Oracle batch %s: %s", batch.id, batch.filename)
            _process_import_batch(batch.id, str(target), replacement)
    except Exception as e:
        log.exception(f"process_queued_oracle_uploads: failed {e}")
    finally:
        oracle_import_lock.release()


def _remote_oracle_config(session):
    from app.models_lol import DataSource

    source = session.exec(select(DataSource).where(DataSource.code == "oracles_elixir")).first()
    if not source:
        return None, None
    try:
        config = json.loads(source.config_json or "{}")
    except json.JSONDecodeError:
        config = {}
    return source, config


def _finish_remote_run(session, run_id, status, started, *, error=None, result=None, skipped=False):
    from app.models_lol import SourceRun

    finished = datetime.now(timezone.utc)
    run = session.get(SourceRun, run_id)
    source, config = _remote_oracle_config(session)
    if not run or not source:
        return
    run.status = status
    run.finished_at = finished
    run.duration_ms = int((finished - started).total_seconds() * 1000)
    run.error_message = error
    source.last_run_at = finished
    source.last_duration_ms = run.duration_ms
    if status == "success":
        source.status = "healthy"
        source.last_success_at = finished
        source.last_error = None
        if skipped:
            run.records_skipped = 1
            source.records_skipped += 1
            run.details_json = str({"unchanged": True})
        else:
            run.records_received = result["games"]
            run.records_inserted = sum(result[key] for key in ("games", "teams", "players"))
            run.details_json = str({"file_size": result["file_size"], "final_url": result["final_url"]})
            source.records_received = result["games"]
            source.records_inserted = run.records_inserted
            source.coverage = "complete"
            config["remote_sha256"] = result["sha256"]
            source.config_json = json.dumps(config, sort_keys=True)
    else:
        source.status = "failed"
        source.last_error = error
    session.add_all([run, source])
    session.commit()


def _process_remote_oracle_run(run_id: int) -> None:
    """Download the configured CSV and update or add the games it contains."""
    from app.models_lol import SourceRun
    from app.services.imports.oracles_elixir_importer import _import_csv_file
    from app.services.imports.remote_oracles_elixir import download_remote_csv
    from app.services.series_builder import rebuild_series

    started = datetime.now(timezone.utc)
    with _session() as session:
        run = session.get(SourceRun, run_id)
        source, config = _remote_oracle_config(session)
        if not run or not source:
            return
        url = (config.get("base_url") or "").strip()
        if not source.enabled or not url or not config.get("auto_refresh", True):
            _finish_remote_run(session, run_id, "failed", started, error="La URL remota no está configurada o está deshabilitada")
            return
        run.status = "running"
        run.started_at = started
        session.add(run)
        session.commit()

        target = Path(settings.lol_history_import_dir) / "remote" / f"oracle-{run_id}.csv"
        try:
            checksum, size, final_url = download_remote_csv(
                url, target, settings.lol_history_remote_max_mb * 1024 * 1024,
            )
            if checksum == config.get("remote_sha256"):
                _finish_remote_run(session, run_id, "success", started, skipped=True)
                return
            result = _import_csv_file(session, str(target), replace=True, prune_missing=False)
            rebuild_series(session)
            _finish_remote_run(
                session, run_id, "success", started,
                result={**result, "sha256": checksum, "file_size": size, "final_url": final_url},
            )
        except Exception as exc:
            session.rollback()
            log.exception("remote Oracle sync failed: %s", exc)
            _finish_remote_run(session, run_id, "failed", started, error=str(exc))
        finally:
            target.unlink(missing_ok=True)


def job_sync_remote_oracles():
    """Run pending manual requests, or the scheduled refresh of the configured remote CSV."""
    if _oracle_import_active() or not oracle_import_lock.acquire(blocking=False):
        return
    try:
        from app.models_lol import SourceRun

        with _session() as session:
            queued = session.exec(select(SourceRun).where(
                SourceRun.source_code == "oracles_elixir",
                SourceRun.job == "remote_sync",
                SourceRun.status == "queued",
            ).order_by(SourceRun.id)).first()
            source, config = _remote_oracle_config(session)
            if queued:
                run_id = queued.id
            elif (
                source
                and source.enabled
                and config.get("auto_refresh", True)
                and (config.get("base_url") or "").strip()
            ):
                run = SourceRun(source_code="oracles_elixir", job="remote_sync", status="queued")
                session.add(run)
                session.commit()
                session.refresh(run)
                run_id = run.id
            else:
                return
        _process_remote_oracle_run(run_id)
    finally:
        oracle_import_lock.release()


def job_process_queued_remote_oracles():
    """Pick up a user-requested remote refresh without waiting for the scheduled interval."""
    if _oracle_import_active() or not oracle_import_lock.acquire(blocking=False):
        return
    try:
        from app.models_lol import SourceRun

        with _session() as session:
            queued = session.exec(select(SourceRun).where(
                SourceRun.source_code == "oracles_elixir",
                SourceRun.job == "remote_sync",
                SourceRun.status == "queued",
            ).order_by(SourceRun.id)).first()
            run_id = queued.id if queued else None
        if run_id:
            _process_remote_oracle_run(run_id)
    finally:
        oracle_import_lock.release()


def job_heartbeat():
    if _oracle_import_active():
        return
    from app.models_lol import WorkerHeartbeat
    with _session() as session:
        row = session.exec(select(WorkerHeartbeat).where(WorkerHeartbeat.worker_name == "pirapire_worker")).first()
        if not row:
            row = WorkerHeartbeat(worker_name="pirapire_worker")
        row.status = "healthy"
        row.last_seen_at = datetime.now(timezone.utc)
        row.detail = "scheduler_running"
        session.add(row)
        session.commit()


def job_precompute_stats():
    if _oracle_import_active():
        log.info("precompute_stats: skipped while an Oracle import holds the database")
        return
    log.info("precompute_stats: start")
    try:
        from app.services.lol_metrics_engine import precompute_upcoming_stats
        with _session() as s:
            result = precompute_upcoming_stats(s)
        log.info(f"precompute_stats: done {result}")
    except Exception as e:
        log.exception(f"precompute_stats: failed {e}")


init_db()
log.info("Worker started. Scheduling jobs...")

scheduler.add_job(job_heartbeat, "interval", minutes=1, id="heartbeat", coalesce=True, max_instances=1, next_run_time=datetime.now(timezone.utc))
scheduler.add_job(job_sync_schedule, "interval", minutes=settings.lol_schedule_interval_minutes, id="sync_schedule", coalesce=True, max_instances=1)
scheduler.add_job(job_sync_datadragon, "interval", minutes=settings.datadragon_interval_minutes, id="sync_datadragon", coalesce=True, max_instances=1)
scheduler.add_job(job_sync_team_logos, "interval", minutes=settings.team_logo_sync_interval_minutes, id="sync_team_logos", coalesce=True, max_instances=1, next_run_time=datetime.now(timezone.utc))
scheduler.add_job(job_import_odds, "interval", minutes=5, id="import_odds", coalesce=True, max_instances=1)
scheduler.add_job(job_import_oracles, "interval", minutes=30, id="import_oracles", coalesce=True, max_instances=1)
scheduler.add_job(job_process_queued_oracle_uploads, "interval", seconds=15, id="process_queued_oracle_uploads", coalesce=True, max_instances=1, next_run_time=datetime.now(timezone.utc))
scheduler.add_job(job_sync_remote_oracles, "interval", minutes=settings.lol_history_remote_poll_minutes, id="sync_remote_oracles", coalesce=True, max_instances=1)
scheduler.add_job(job_process_queued_remote_oracles, "interval", seconds=15, id="process_queued_remote_oracles", coalesce=True, max_instances=1, next_run_time=datetime.now(timezone.utc))
scheduler.add_job(job_precompute_stats, "interval", minutes=30, id="precompute_stats", coalesce=True, max_instances=1)

scheduler.start()
log.info("Worker running. Press Ctrl+C to stop.")

try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    log.info("Worker stopped.")
    scheduler.shutdown()
