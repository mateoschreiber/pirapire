from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import settings
from sqlmodel import Session

from .database import engine, init_db
from .routers import health, lol_api, pages, sources


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    from .services.lol_team_aliases import synchronize_known_aliases
    with Session(engine) as session:
        synchronize_known_aliases(session)
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(lol_api.router)
app.include_router(pages.router)
app.include_router(sources.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
