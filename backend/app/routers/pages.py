from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(
        request=request, name="dashboard.html", context={"page": "dashboard"}
    )


@router.get("/lol/matches/{match_key}", response_class=HTMLResponse)
async def match_detail(request: Request, match_key: str):
    return templates.TemplateResponse(
        request=request,
        name="match_detail.html",
        context={"page": "match-detail", "match_key": match_key},
    )


@router.get("/football", response_class=HTMLResponse)
async def football_dashboard(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="football_dashboard.html",
        context={"page": "football-dashboard"},
    )


@router.get("/sources", response_class=HTMLResponse)
async def sources_page(request: Request):
    return templates.TemplateResponse(
        request=request, name="sources.html", context={"page": "sources"}
    )
