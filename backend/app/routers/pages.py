from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse(request=request, name="dashboard.html")


@router.get("/lol/matches/{match_key}", response_class=HTMLResponse)
async def match_detail(request: Request, match_key: str):
    return templates.TemplateResponse(request=request, name="match_detail.html", context={"match_key": match_key})
