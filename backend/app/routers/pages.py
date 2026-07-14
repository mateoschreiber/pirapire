from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select, func

from ..config import settings
from ..database import engine
from ..models_football import (
    FootballCompetition,
    FootballMatch,
    FootballStanding,
    FootballTeam,
)
from ..models_history import ComboHistory, PredictionHistory
from ..models_imports import ImportedOdds, ManualImportBatch
from ..models_aposta import ApostaEvent
from ..models_lol import LolChampion, LolPatch
from ..models_markets import MarketCatalog
from ..models_sources import SourceRun
from ..services import source_registry as registry
from ..services import source_resolver
from ..utils import datetime_utils

router = APIRouter(tags=["ui"], include_in_schema=False)
templates = Jinja2Templates(directory="app/templates")


def render(request: Request, template: str, active_page: str, **extra):
    context = {
        "active_page": active_page,
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "database_url": settings.database_url,
        "build_commit": settings.build_commit,
        "tz_name": settings.app_timezone,
        "tz_offset": datetime_utils.offset_str(),
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
            "imported_odds": _count(session, ImportedOdds),
            "import_batches": _count(session, ManualImportBatch),
            "markets": _count(session, MarketCatalog),
            "predictions": _count(session, PredictionHistory),
            "combos": _count(session, ComboHistory),
            "last_update": last_update,
            "last_status": last_status,
        }


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    from ..models_imports import ImportedOdds
    from ..models_recommendations import BetRecommendation, RecommendationRun
    from ..models_lol import LolPlayerGameStat

    counts = _dashboard_counts()
    with Session(engine) as session:
        # Get current Aposta odds count
        aposta_count = (
            session.exec(
                select(func.count())
                .select_from(ImportedOdds)
                .where(ImportedOdds.source_name == "aposta_la", ImportedOdds.is_current)
            ).one()
            or 0
        )

        # Get upcoming scheduled events only (Phase 4D1: excludes finished/historical)
        from ..models_aposta import ApostaEvent

        scheduled_keys = {
            ev.event_key
            for ev in session.exec(
                select(ApostaEvent.event_key).where(
                    ApostaEvent.local_event_state == "scheduled",
                    ApostaEvent.event_key.is_not(None),
                )
            ).all()
        }
        rows = session.exec(
            select(ImportedOdds)
            .where(ImportedOdds.source_name == "aposta_la", ImportedOdds.is_current,
                   ImportedOdds.event_key.in_(scheduled_keys) if scheduled_keys else True)
            .order_by(ImportedOdds.event_date_sort)
        ).all()
        events_dict = {}
        for r in rows:
            k = r.event_key or (r.team_a or "") + "|" + (r.team_b or "") + "|" + (r.competition or "") + "|" + (r.event_date_sort or "")
            if k not in events_dict:
                events_dict[k] = {
                    "team_a": r.team_a,
                    "team_b": r.team_b,
                    "competition": r.competition,
                    "event_date": r.kickoff_utc or r.event_date_sort,
                    "event_date_py": datetime_utils.event_time_display(
                        r.kickoff_utc or r.event_date_sort, r.event_time_status
                    ),
                    "event_time_status": r.event_time_status,
                    "sport": r.sport,
                    "markets": 0,
                    "event_id": r.id,
                    "event_key": r.event_key,
                }
            events_dict[k]["markets"] += 1
        events = sorted(events_dict.values(), key=lambda e: e.get("event_date") or "")[
            :20
        ]

        # Get latest bets
        latest_run = session.exec(
            select(RecommendationRun).order_by(RecommendationRun.id.desc())
        ).first()
        bets = []
        if latest_run:
            bets = session.exec(
                select(BetRecommendation)
                .where(BetRecommendation.run_id == latest_run.id)
                .limit(10)
            ).all()

        # LoL player count
        lol_players = (
            session.exec(
                select(func.count(func.distinct(LolPlayerGameStat.player_name))).where(
                    LolPlayerGameStat.player_name.isnot(None)
                )
            ).one()
            or 0
        )

    return render(
        request,
        "dashboard.html",
        "dashboard",
        counts=counts,
        aposta_odds=aposta_count,
        football_matches=counts.get("football_matches", 0),
        lol_games=480,
        lol_players=lol_players,
        events=events,
        bets=bets,
    )


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


@router.get("/markets/ui", response_class=HTMLResponse)
def markets_page(request: Request):
    return render(request, "markets.html", "markets")


@router.get("/imports/ui", response_class=HTMLResponse)
def imports_page(request: Request):
    return render(request, "imports.html", "imports")


@router.get("/aposta/ui", response_class=HTMLResponse)
def aposta_page(request: Request):
    return render(request, "aposta.html", "aposta")


@router.get("/recommendations/ui", response_class=HTMLResponse)
def recommendations_page(request: Request):
    return render(request, "recommendations.html", "recommendations")


@router.get("/events/{event_key}", response_class=HTMLResponse)
def event_detail_page(request: Request, event_key: str):
    with Session(engine) as session:
        if event_key.isdigit():
            rows = session.exec(select(ImportedOdds).where(ImportedOdds.id == int(event_key))).all()
            keys = {row.event_key for row in rows if row.event_key}
            if not keys:
                raise HTTPException(status_code=404, detail="Legacy event id not found")
            if len(keys) != 1:
                raise HTTPException(status_code=409, detail="Legacy event id resolves ambiguously")
            return RedirectResponse(f"/events/{keys.pop()}", status_code=308)
        canonical = session.exec(select(ApostaEvent).where(ApostaEvent.event_key == event_key)).first()
        if canonical is None:
            raise HTTPException(status_code=404, detail="Event not found")
        odds = session.exec(select(ImportedOdds).where(ImportedOdds.event_key == event_key, ImportedOdds.is_current)).all()
        if not odds:
            raise HTTPException(status_code=404, detail="Event has no active odds")
        odd = odds[0]
        event = {
            "event_key": event_key,
            "team_a": canonical.team_a,
            "team_b": canonical.team_b,
            "competition": canonical.competition,
            "sport": canonical.sport,
            "event_date": canonical.kickoff_utc,
            "event_date_display": datetime_utils.event_time_display(canonical.kickoff_utc, odd.event_time_status),
            "total_odds": len(odds),
            "market_count": len({o.canonical_market_id for o in odds}),
        }
    return render(request, "event_detail.html", "dashboard", event=event)
