from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import settings
from .database import engine, init_db
from .routers import health, lol_api, pages


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(lol_api.router)
app.include_router(pages.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
