import logging
import signal
import sys
sys.path.insert(0, '/app')
from app.database import engine, init_db
from app.config import settings
from sqlmodel import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pirapire.worker')

def run_aposta_sync():
    from app.services.aposta_sync import sync
    with Session(engine) as session:
        try:
            result = sync(session)
            count = result.get('imported', 0)
            logger.info('Aposta: %s odds', count)
        except Exception as e:
            logger.warning('Aposta sync error: %s', e)

def run_wc_squad_sync():
    try:
        from app.services.import_wc_squads import import_wc_squads
        n = import_wc_squads()
        logging.getLogger('pirapire.worker').info('WC squads: %s players', n)
    except Exception as e:
        logging.getLogger('pirapire.worker').warning('WC squads sync error: %s', e)


def run_historical_ingestion():
    from app.services.historical_ingestion import run
    with Session(engine) as session:
        try:
            logger.info("Historical ingestion: %s", run(session))
        except Exception as e:
            logger.warning("Historical ingestion error: %s", e)


def run_fresh_football():
    from app.services.fresh_football import run as ff_run
    with Session(engine) as session:
        try:
            res = ff_run(session)
            logger.info("Fresh football: status=%s teams=%s", res.get("status"),
                        {k: v.get("eligible") for k, v in (res.get("teams") or {}).items()})
        except Exception as e:
            logger.warning("Fresh football error: %s", e)


def run_descriptive_stats():
    from app.services.descriptive_stats import rebuild_all
    with Session(engine) as session:
        try:
            logger.info("Descriptive stats: %s", rebuild_all(session))
        except Exception as e:
            logger.warning("Descriptive stats error: %s", e)


def run_event_refresh():
    """Process the coalesced refresh queue: one task per event, instance-locked."""
    from sqlmodel import select
    from app.models_aposta import ApostaEvent
    from app.services.refresh_queue import claim_task, release_task, enqueue_scheduled_events
    from app.services.descriptive_stats import compute_event
    from app.services.event_lifecycle import refresh_states, SCHEDULED

    worker_id = "worker-1"
    with Session(engine) as session:
        try:
            state_counts = refresh_states(session)
            logger.info("Lifecycle states: %s", state_counts)
            n = enqueue_scheduled_events(session)
            if n:
                logger.info("Enqueued %s scheduled events for refresh", n)
            processed = 0
            max_batch = 5
            for _ in range(max_batch):
                task = claim_task(session, worker_id)
                if task is None:
                    break
                try:
                    ev = session.exec(
                        select(ApostaEvent).where(ApostaEvent.event_key == task.event_key)
                    ).first()
                    if ev is None or ev.local_event_state != SCHEDULED:
                        release_task(session, task.event_key, True)
                        continue
                    compute_event(session, task.event_key)
                    release_task(session, task.event_key, True)
                    processed += 1
                except Exception as exc:
                    logger.warning("Refresh task %s error: %s", task.event_key, exc)
                    release_task(session, task.event_key, False)
            if processed:
                logger.info("Event refresh: processed %s tasks", processed)
        except Exception as e:
            logger.warning("Event refresh error: %s", e)


def run_sports_sync():
    from app.services.live_source_sync import sync_if_stale
    with Session(engine) as session:
        try:
            sync_if_stale(session)
            logger.info('Sports sync done')
        except Exception as e:
            logger.warning('Sports sync error: %s', e)

if __name__ == '__main__':
    logger.info('Pirapire worker starting')
    init_db()
    scheduler = BackgroundScheduler()
    scheduler.add_job(run_aposta_sync, IntervalTrigger(minutes=settings.worker_aposta_sync_minutes), id='aposta', coalesce=True, max_instances=1)
    scheduler.add_job(run_sports_sync, IntervalTrigger(hours=settings.worker_sports_sync_hours), id='sports', coalesce=True, max_instances=1)
    scheduler.add_job(run_historical_ingestion, IntervalTrigger(hours=settings.worker_historical_ingestion_hours), id='historical-ingestion', coalesce=True, max_instances=1)
    scheduler.add_job(run_fresh_football, IntervalTrigger(hours=settings.worker_fresh_football_hours), id='fresh-football', coalesce=True, max_instances=1)
    scheduler.add_job(run_descriptive_stats, IntervalTrigger(hours=settings.worker_descriptive_stats_hours), id='descriptive-stats', coalesce=True, max_instances=1)
    scheduler.add_job(run_event_refresh, IntervalTrigger(minutes=settings.worker_event_refresh_minutes), id='event-refresh', coalesce=True, max_instances=1)
    scheduler.add_job(run_wc_squad_sync, IntervalTrigger(hours=settings.worker_wc_squads_hours), id='wc_squads', coalesce=True, max_instances=1)
    scheduler.start()
    logger.info('Scheduler started with configured extraction and statistics intervals')
    run_sports_sync()
    run_aposta_sync()
    signal.pause()