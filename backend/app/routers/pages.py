from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from ..config import settings

router = APIRouter(tags=["ui"], include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")


def render(request: Request, template: str, active_page: str, **extra):
    context = {
        "active_page": active_page,
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "database_url": settings.database_url,
    }
    context.update(extra)
    return templates.TemplateResponse(request, template, context)


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return render(request, "dashboard.html", "dashboard")


@router.get("/sports/ui", response_class=HTMLResponse)
def sports_page(request: Request):
    return render(request, "sports.html", "sports")


@router.get("/teams/ui", response_class=HTMLResponse)
def teams_page(request: Request):
    return render(request, "teams.html", "teams")


@router.get("/matches/ui", response_class=HTMLResponse)
def matches_page(request: Request):
    return render(request, "matches.html", "matches")


@router.get("/odds/ui", response_class=HTMLResponse)
def odds_page(request: Request):
    return render(request, "odds.html", "odds")


@router.get("/combo/ui", response_class=HTMLResponse)
def combo_page(request: Request):
    return render(request, "combo.html", "combo")


@router.get("/history/ui", response_class=HTMLResponse)
def history_page(request: Request):
    return render(request, "history.html", "history")


@router.get("/settings/ui", response_class=HTMLResponse)
def settings_page(request: Request):
    return render(request, "settings.html", "settings")
