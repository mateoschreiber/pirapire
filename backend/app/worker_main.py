import logging
import signal
import sys
sys.path.insert(0, '/app')
from app.database import engine, init_db
from sqlmodel import Session
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('pirapire.worker')

def run_aposta_sync():
    from app.services.aposta_sync import sync
    from app.services.recommender.recommendation_service import run as rec_run
    with Session(engine) as session:
        try:
            result = sync(session)
            count = result.get('imported', 0)
            logger.info('Aposta: %s odds', count)
            if count > 0:
                r = rec_run(session, mode='balanced')
                logger.info('Recs: %s singles', r.get('singles', 0))
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
    scheduler.add_job(run_aposta_sync, IntervalTrigger(minutes=12), id='aposta', coalesce=True, max_instances=1)
    scheduler.add_job(run_sports_sync, IntervalTrigger(hours=4), id='sports', coalesce=True, max_instances=1)
    scheduler.add_job(run_historical_ingestion, IntervalTrigger(hours=1), id='historical-ingestion', coalesce=True, max_instances=1)
    scheduler.add_job(run_fresh_football, IntervalTrigger(hours=1), id='fresh-football', coalesce=True, max_instances=1)
    scheduler.add_job(run_wc_squad_sync, IntervalTrigger(hours=24), id='wc_squads', coalesce=True, max_instances=1)
    scheduler.start()
    logger.info('Scheduler: Aposta 12min, Sports 4h')
    run_sports_sync()
    run_aposta_sync()
    signal.pause()
