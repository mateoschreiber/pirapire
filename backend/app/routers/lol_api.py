import re
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models_lol import LolMatchEvent, LolOddsSnapshot, LolTeamOdd

router = APIRouter(prefix="/api/lol")

COMPETITIONS = (
    ("LCK", "LCK"),
    ("LPL", "LPL"),
    ("LEC", "LEC"),
    ("LCS", "LCS"),
    ("CBLOL", "CBLOL"),
    ("LCP", "LCP"),
    ("WORLDS", "WORLDS"),
    ("MSI", "MSI"),
    ("FIRST_STAND", "FIRST STAND"),
    ("EWC", "EWC"),
)
COMPETITION_LABELS = dict(COMPETITIONS)

OFFICIAL_COMPETITION_ROSTERS_2026 = {
    "LCK": {
        "teams": (
            "Gen.G Esports", "T1", "NONGSHIM RED FORCE", "DN SOOPers", "HANJIN BRION",
            "Hanwha Life Esports", "Dplus KIA", "kt Rolster", "BNK FEARX", "KIWOOM DRX",
        ),
        "source_url": "https://lolesports.com/en-US/tournament/115548106590082745/overview",
        "status": "official",
    },
    "LPL": {
        "teams": (
            "Anyone's Legend", "BILIBILI GAMING", "Invictus Gaming", "Beijing JDG Esports",
            "Shenzhen NINJAS IN PYJAMAS", "Xi'an Team WE", "TOP ESPORTS", "WeiboGaming",
            "EDWARD GAMING", "LGD GAMING", "Suzhou LNG Esports", "Oh My God",
            "THUNDER TALK GAMING", "Ultra Prime",
        ),
        "source_url": "https://lolesports.com/en-US/tournament/115615907996665826/overview",
        "status": "official",
    },
    "LEC": {
        "teams": (
            "Team Heretics", "Natus Vincere", "Team Vitality", "Shifters", "GIANTX",
            "SK Gaming", "Movistar KOI", "Fnatic", "Karmine Corp", "G2 Esports",
        ),
        "source_url": "https://lolesports.com/en-US/tournament/115548681802226458/overview",
        "status": "official",
    },
    "LCS": {
        "teams": (
            "Sentinels", "Cloud9 Kia", "Dignitas", "Disguised", "FlyQuest", "LYON",
            "Shopify Rebellion", "Team Liquid Alienware",
        ),
        "source_url": "https://lolesports.com/news/lcs-2026-address",
        "status": "official",
    },
    "CBLOL": {
        "teams": (
            "Fluxo W7M", "FURIA", "LEVIATÁN", "LOS", "LOUD", "paiN Gaming",
            "RED Kalunga", "Vivo Keyd Stars",
        ),
        "source_url": "https://lolesports.com/en-US/tournament/115565518151768348/overview",
        "status": "official",
    },
    "LCP": {
        "teams": (
            "CTBC Flying Oyster", "DetonatioN FocusMe", "Relove Deep Cross Gaming",
            "GAM Esports", "Ground Zero Gaming", "MVK Esports",
            "Fukuoka SoftBank HAWKS gaming", "Team Secret Whales",
        ),
        "source_url": "https://lolesports.com/en-US/tournament/115570728597462574/overview",
        "status": "official",
    },
    "WORLDS": {
        "teams": (),
        "source_url": "https://lolesports.com/en-US/news/msi-and-worlds-updates",
        "status": "not_published",
    },
    "MSI": {
        "teams": (
            "BILIBILI GAMING", "TOP ESPORTS", "Hanwha Life Esports", "T1",
            "G2 Esports", "Karmine Corp", "LYON", "Team Liquid Alienware",
            "Team Secret Whales", "Relove Deep Cross Gaming", "FURIA",
        ),
        "source_url": "https://lolesports.com/en-US/news/msi-",
        "status": "official",
    },
    "FIRST_STAND": {
        "teams": (
            "BILIBILI GAMING", "Beijing JDG Esports", "Gen.G Esports", "BNK FEARX",
            "G2 Esports", "LYON", "Team Secret Whales", "LOUD",
        ),
        "source_url": "https://lolesports.com/en-US/leagues/first_stand",
        "status": "official",
    },
    "EWC": {
        "teams": (),
        "source_url": "https://resources.esportsworldcup.com/en",
        "status": "not_published",
    },
}

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _competition_code(league: str | None, tournament: str | None = None) -> str | None:
    league_text = (league or "").strip().upper()
    combined = f"{league_text} {(tournament or '').strip().upper()}"
    if "ESPORTS WORLD CUP" in combined:
        return "EWC"
    if "FIRST STAND" in combined or "FIST STAND" in combined:
        return "FIRST_STAND"
    if "MID-SEASON INVITATIONAL" in combined or re.search(r"(^|[^A-Z])MSI([^A-Z]|$)", combined):
        return "MSI"
    if "WORLD CHAMPIONSHIP" in combined or "WORLDS" in combined:
        return "WORLDS"
    if re.match(r"^LTA NORTH(?:/|$)", league_text):
        return "LCS"
    if re.match(r"^LTA SOUTH(?:/|$)", league_text):
        return "CBLOL"
    for code in ("LCK", "LPL", "LEC", "LCS", "CBLOL", "LCP"):
        if re.match(rf"^{code}(?:/|$)", league_text):
            return code
    return None

def _odds_for_match(session: Session, match: LolMatchEvent) -> dict:
    snapshot = session.exec(
        select(LolOddsSnapshot)
        .where(LolOddsSnapshot.match_event_id == match.id)
        .where(LolOddsSnapshot.is_current == True)  # noqa: E712
        .order_by(LolOddsSnapshot.captured_at.desc())
        .limit(1)
    ).first()
    odds_a = odds_b = None
    if snapshot:
        for odd in session.exec(select(LolTeamOdd).where(LolTeamOdd.snapshot_id == snapshot.id)).all():
            if odd.team_name == match.team_a:
                odds_a = odd.decimal_odds
            elif odd.team_name == match.team_b:
                odds_b = odd.decimal_odds
    available = odds_a is not None and odds_b is not None
    return {
        "odds_a": odds_a,
        "odds_b": odds_b,
        "odds_provider": snapshot.provider if snapshot else None,
        "odds_captured_at": snapshot.captured_at.isoformat() if snapshot else None,
        "odds_available": available,
        "odds_status": "available" if available else "not_captured",
        "odds_message": None if available else "Sin captura de cuotas. Oracle's Elixir no incluye datos de apuestas.",
    }


def _match_view(session: Session, match: LolMatchEvent) -> dict:
    code = _competition_code(match.league, match.tournament)
    return {
        "match_key": match.match_key,
        "competition_code": code,
        "competition": COMPETITION_LABELS.get(code, match.league or match.tournament or "N/D"),
        "league": match.league,
        "tournament": match.tournament,
        "team_a": match.team_a,
        "team_b": match.team_b,
        "start_time_utc": match.start_time_utc.isoformat(),
        "best_of": match.best_of,
        "status": match.status,
        **_odds_for_match(session, match),
    }


def _competition_summary(events: list[LolMatchEvent], upcoming: list[LolMatchEvent], year: int) -> list[dict]:
    upcoming_counts = {code: 0 for code, _ in COMPETITIONS}
    for event in upcoming:
        code = _competition_code(event.league, event.tournament)
        if code in upcoming_counts:
            upcoming_counts[code] += 1

    result = []
    for code, label in COMPETITIONS:
        relevant = [
            event for event in events
            if event.start_time_utc.year == year and _competition_code(event.league, event.tournament) == code
        ]
        discovered_teams = sorted({
            team.strip()
            for event in relevant
            for team in (event.team_a, event.team_b)
            if team and team.strip().upper() not in {"TBD", "TBA", "UNKNOWN"}
        }, key=str.casefold)
        official = OFFICIAL_COMPETITION_ROSTERS_2026.get(code) if year == 2026 else None
        teams = list(official["teams"]) if official else discovered_teams
        roster_status = official["status"] if official else ("calendar_derived" if teams else "not_published")
        result.append({
            "code": code,
            "label": label,
            "season": year,
            "qualified_teams": teams,
            "team_count": len(teams),
            "upcoming_matches": upcoming_counts[code],
            "coverage": "available" if teams else "not_published",
            "roster_status": roster_status,
            "official_source_url": official["source_url"] if official else None,
        })
    return result


@router.get("/matches/upcoming")
def upcoming_matches(
    hours: int = Query(default=48, ge=1, le=720),
    session: Session = Depends(get_session),
):
    now = _now_utc()
    window_end = now + timedelta(hours=hours)
    scheduled = session.exec(
        select(LolMatchEvent)
        .where(LolMatchEvent.start_time_utc >= now)
        .where(LolMatchEvent.start_time_utc <= window_end)
        .where(LolMatchEvent.status == "scheduled")
        .order_by(LolMatchEvent.start_time_utc.asc())
    ).all()
    allowed = [event for event in scheduled if _competition_code(event.league, event.tournament)]
    all_events = session.exec(select(LolMatchEvent)).all()
    return {
        "matches": [_match_view(session, match) for match in allowed],
        "competitions": _competition_summary(all_events, allowed, now.year),
        "allowed_competitions": [label for _, label in COMPETITIONS],
        "count": len(allowed),
        "window_hours": hours,
        "timezone": settings.app_timezone,
    }


@router.get("/matches/{match_key}")
def get_match(match_key: str, session: Session = Depends(get_session)):
    match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")
    return {
        **_match_view(session, match),
        "source_name": match.source_name,
        "source_url": match.source_url,
    }


@router.get("/matches/{match_key}/statistics")
def get_match_statistics(match_key: str, session: Session = Depends(get_session)):
    from ..services.lol_metrics_engine import compute_match_statistics

    result = compute_match_statistics(session, match_key)
    if not result:
        raise HTTPException(status_code=404, detail="Match not found")
    payload, coverage = result
    return {
        "match_key": match_key,
        "status": "computed",
        "payload": payload,
        "coverage": coverage,
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }
