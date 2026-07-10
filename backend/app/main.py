import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import engine, init_db
from .routers import (
    dashboard,
    aposta,
    combo,
    data,
    health,
    history,
    imports,
    lol_history,
    markets,
    odds,
    pages,
    recommendations,
    source_runs,
    sources,
)

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger('pirapire')


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info('Starting %s (%s)', settings.app_name, settings.app_env)
    init_db()
    _seed_markets_safe()
    _seed_lol_catalog_safe()
    from apscheduler.schedulers.background import BackgroundScheduler
    from apscheduler.triggers.interval import IntervalTrigger
    scheduler = BackgroundScheduler()
    scheduler.add_job(_scheduled_aposta_sync, IntervalTrigger(minutes=15), id='aposta_sync')
    scheduler.add_job(_scheduled_football_sync, IntervalTrigger(hours=6), id='football_sync')
    scheduler.start()
    logger.info('Scheduler started: Aposta every 15min, Football every 6h')

    yield


def _seed_markets_safe() -> None:
    try:
        from sqlmodel import Session

        from .services.market_catalog import seed_catalog

        with Session(engine) as session:
            seed_catalog(session)
    except Exception as exc:
        logger.warning('market catalog seed skipped: %s', exc)


def _seed_lol_catalog_safe() -> None:
    try:
        from sqlmodel import Session

        from .services.lol_league_catalog import seed_catalog

        with Session(engine) as session:
            seed_catalog(session)
    except Exception as exc:
        logger.warning('LoL league catalog seed skipped: %s', exc)


def _scheduled_aposta_sync():
    try:
        from sqlmodel import Session
        from .services.aposta_sync import sync as aposta_sync
        from .services.recommender.recommendation_service import run as rec_run
        with Session(engine) as session:
            result = aposta_sync(session)
            if result.get('imported', 0) > 0:
                rec_run(session, mode='balanced')
    except Exception as e:
        logger.warning('Scheduled Aposta sync failed: %s', e)


def _scheduled_football_sync():
    try:
        from .services.sync.football_sync import sync as fb_sync
        fb_sync()
    except Exception as e:
        logger.warning('Scheduled football sync failed: %s', e)


app = FastAPI(
    title=settings.app_name,
    description='Sistema analitico de cuotas deportivas. No automatiza apuestas reales.',
    version='0.3.0',
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(pages.router)
app.include_router(odds.router)
app.include_router(combo.router)
app.include_router(sources.router)
app.include_router(source_runs.router)
app.include_router(data.router)
app.include_router(markets.router)
app.include_router(imports.router)
app.include_router(history.router)
app.include_router(lol_history.router)
app.include_router(dashboard.router)
app.include_router(aposta.router)
app.include_router(recommendations.router)

app.mount('/static', StaticFiles(directory='app/static'), name='static')


@app.get('/api/info', tags=['root'])
def api_info() -> dict:
    return {
        'app': settings.app_name,
        'env': settings.app_env,
        'docs': '/docs',
        'health': '/health',
        'disclaimer': 'Sistema analitico. No automatiza apuestas reales.',
    }
