from fastapi import APIRouter

from ..config import settings

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/api/info")
def api_info() -> dict:
    return {
        "app": settings.app_name,
        "env": settings.app_env,
        "build_commit": settings.build_commit,
        "timezone": settings.app_timezone,
        "health": "/health",
        "docs": "/docs",
    }
