import sys, os, time, logging
from datetime import datetime, timezone
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


def _session():
    return Session(engine)


def job_sync_schedule():
    log.info("sync_schedule: start")
    try:
        from app.services.sync.lol_sync import sync_leaguepedia_schedule
        with _session() as s:
            result = sync_leaguepedia_schedule(s)
        log.info(f"sync_schedule: done {result}")
    except Exception as e:
        log.exception(f"sync_schedule: failed {e}")


def job_sync_datadragon():
    log.info("sync_datadragon: start")
    try:
        from app.services.sync.lol_sync import sync_datadragon
        with _session() as s:
            result = sync_datadragon(s)
        log.info(f"sync_datadragon: done {result}")
    except Exception as e:
        log.exception(f"sync_datadragon: failed {e}")


def job_import_odds():
    log.info("import_odds: start")
    try:
        from app.services.lol_odds_importer import import_odds_directory
        with _session() as s:
            result = import_odds_directory(s)
        log.info(f"import_odds: done {result}")
    except Exception as e:
        log.exception(f"import_odds: failed {e}")


def job_import_oracles():
    log.info("import_oracles: start")
    try:
        from app.services.imports.oracles_elixir_importer import import_oracles_inbox
        with _session() as s:
            result = import_oracles_inbox(s)
        log.info(f"import_oracles: done {result}")
    except Exception as e:
        log.exception(f"import_oracles: failed {e}")


def job_heartbeat():
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
scheduler.add_job(job_sync_schedule, "interval", minutes=settings.lol_schedule_interval_minutes, id="sync_schedule", coalesce=True, max_instances=1, next_run_time=datetime.now(timezone.utc))
scheduler.add_job(job_sync_datadragon, "interval", minutes=settings.datadragon_interval_minutes, id="sync_datadragon", coalesce=True, max_instances=1, next_run_time=datetime.now(timezone.utc))
scheduler.add_job(job_import_odds, "interval", minutes=5, id="import_odds", coalesce=True, max_instances=1)
scheduler.add_job(job_import_oracles, "interval", minutes=30, id="import_oracles", coalesce=True, max_instances=1)
scheduler.add_job(job_precompute_stats, "interval", minutes=30, id="precompute_stats", coalesce=True, max_instances=1)

scheduler.start()
log.info("Worker running. Press Ctrl+C to stop.")

try:
    while True:
        time.sleep(60)
except KeyboardInterrupt:
    log.info("Worker stopped.")
    scheduler.shutdown()
