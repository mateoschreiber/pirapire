import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import settings
from .database import init_db
from .routers import combo, health, matches, odds, sports, teams

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger("pirapire")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s (%s)", settings.app_name, settings.app_env)
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Sistema analitico de cuotas deportivas. No automatiza apuestas reales.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(sports.router)
app.include_router(teams.router)
app.include_router(matches.router)
app.include_router(odds.router)
app.include_router(combo.router)


@app.get("/", tags=["root"])
def root() -> dict:
    return {
        "app": settings.app_name,
        "env": settings.app_env,
        "docs": "/docs",
        "health": "/health",
        "disclaimer": "Sistema analitico. No automatiza apuestas reales.",
    }
