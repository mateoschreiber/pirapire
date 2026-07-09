from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from ..config import settings
from ..database import engine
from ..models_football import (
    FootballCompetition,
    FootballMatch,
    FootballStanding,
    FootballTeam,
)
from ..models_lol import LolChampion, LolPatch
from ..models_sources import SourceRun
from ..services import source_registry as registry
from ..services import source_resolver

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


def _count(session: Session, model) -> int:
    return len(session.exec(select(model)).all())


def _dashboard_counts() -> dict:
    with Session(engine) as session:
        last_run = session.exec(select(SourceRun).order_by(SourceRun.id.desc())).first()
        last_update = None
        last_status = None
        if last_run is not None:
            last_update = last_run.finished_at or last_run.started_at
            last_status = last_run.status
        return {
            "football_competitions": _count(session, FootballCompetition),
            "football_teams": _count(session, FootballTeam),
            "football_matches": _count(session, FootballMatch),
            "football_standings": _count(session, FootballStanding),
            "lol_patches": _count(session, LolPatch),
            "lol_champions": _count(session, LolChampion),
            "last_update": last_update,
            "last_status": last_status,
        }


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    return render(request, "dashboard.html", "dashboard", counts=_dashboard_counts())


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


def _source_role(src_dict: dict) -> str:
    status = src_dict["status"]
    if status != "enabled":
        return status  # disabled_missing_env / disabled_reference_only
    for data_type in src_dict["use_for"]:
        primary = source_resolver.pick_primary(src_dict["sport"], data_type)
        if primary and primary["slug"] == src_dict["slug"]:
            return "primary"
    return "fallback"


def _sources_context(sport: str) -> dict:
    ordered = sorted(registry.sources_for(sport), key=lambda s: s["rank"], reverse=True)
    sources = []
    for raw in ordered:
        item = registry.as_dict(raw)
        item["role"] = _source_role(item)
        sources.append(item)
    data_types = sorted({dt for s in ordered for dt in s["use_for"]})
    primary = {}
    for data_type in data_types:
        top = source_resolver.pick_primary(sport, data_type)
        primary[data_type] = top["slug"] if top else None
    return {"sources": sources, "primary": primary}


@router.get("/sources/ui", response_class=HTMLResponse)
def sources_page(request: Request):
    return render(
        request,
        "sources.html",
        "sources",
        football=_sources_context("football"),
        lol=_sources_context("lol"),
    )


@router.get("/source-runs/ui", response_class=HTMLResponse)
def source_runs_page(request: Request):
    return render(request, "source_runs.html", "source_runs")


@router.get("/data/football/ui", response_class=HTMLResponse)
def data_football_page(request: Request):
    return render(request, "data_football.html", "data_football")


@router.get("/data/lol/ui", response_class=HTMLResponse)
def data_lol_page(request: Request):
    return render(request, "data_lol.html", "data_lol")
