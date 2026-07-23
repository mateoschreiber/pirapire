"""Import fixtures from supported football providers into the local database."""

import json
import urllib.parse
import urllib.request
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from ...config import settings
from ...models_football import FootballMatchEvent
from ...models_lol import DataSource


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed


def _request_json(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def _api_football_fixtures(config: dict) -> list[dict]:
    base_url = config["base_url"].rstrip("/")
    payload = _request_json(
        f"{base_url}/fixtures?next=50",
        {"x-apisports-key": config["api_key"], "User-Agent": settings.leaguepedia_user_agent},
    )
    if payload.get("errors"):
        details = "; ".join(str(value) for value in payload["errors"].values())
        raise ValueError(f"API-Football rechazó la clave: {details}")
    fixtures = []
    for item in payload.get("response", []):
        fixture, league, teams = item.get("fixture", {}), item.get("league", {}), item.get("teams", {})
        home, away = teams.get("home", {}), teams.get("away", {})
        if not fixture.get("id") or not fixture.get("date") or not home.get("name") or not away.get("name"):
            continue
        short_status = fixture.get("status", {}).get("short", "NS")
        fixtures.append({
            "source_match_id": str(fixture["id"]),
            "competition_name": league.get("name"),
            "season": str(league["season"]) if league.get("season") is not None else None,
            "home_team_name": home["name"],
            "away_team_name": away["name"],
            "start_time_utc": _parse_datetime(fixture["date"]),
            "status": "scheduled" if short_status in {"NS", "TBD", "PST"} else "finished" if short_status in {"FT", "AET", "PEN"} else short_status.lower(),
            "home_score": (item.get("goals") or {}).get("home"),
            "away_score": (item.get("goals") or {}).get("away"),
            "venue": (fixture.get("venue") or {}).get("name"),
        })
    return fixtures


def _football_data_fixtures(config: dict) -> list[dict]:
    today = datetime.now(UTC).date()
    query = urllib.parse.urlencode({"dateFrom": today.isoformat(), "dateTo": (today + timedelta(days=14)).isoformat()})
    payload = _request_json(
        f"{config['base_url'].rstrip('/')}/matches?{query}",
        {"X-Auth-Token": config["api_key"], "User-Agent": settings.leaguepedia_user_agent},
    )
    if payload.get("message"):
        raise ValueError(f"football-data.org respondió: {payload['message']}")
    fixtures = []
    for item in payload.get("matches", []):
        home, away = item.get("homeTeam", {}), item.get("awayTeam", {})
        if item.get("id") is None or not item.get("utcDate") or not home.get("name") or not away.get("name"):
            continue
        status = item.get("status", "SCHEDULED")
        score = item.get("score") or {}
        full_time = score.get("fullTime") or {}
        fixtures.append({
            "source_match_id": str(item["id"]),
            "competition_name": (item.get("competition") or {}).get("name"),
            "season": str(((item.get("season") or {}).get("startDate") or "")[:4]) or None,
            "home_team_name": home["name"],
            "away_team_name": away["name"],
            "start_time_utc": _parse_datetime(item["utcDate"]),
            "status": "scheduled" if status in {"SCHEDULED", "TIMED"} else "finished" if status == "FINISHED" else status.lower(),
            "home_score": full_time.get("home"),
            "away_score": full_time.get("away"),
            "venue": item.get("venue"),
        })
    return fixtures


def fetch_fixtures(source: DataSource) -> list[dict]:
    try:
        config = json.loads(source.config_json or "{}")
    except json.JSONDecodeError as exc:
        raise ValueError("La configuración de la fuente no es válida") from exc
    if not config.get("base_url") or not config.get("api_key"):
        raise ValueError("La fuente requiere URL base y clave API")
    if source.code == "api_football":
        return _api_football_fixtures(config)
    if source.code == "football_data":
        return _football_data_fixtures(config)
    raise ValueError("No hay adaptador para esta fuente de fútbol")


def import_fixtures(session: Session, source: DataSource) -> dict[str, int]:
    fixtures = fetch_fixtures(source)
    inserted = updated = skipped = 0
    for fixture in fixtures:
        match_key = f"{source.code}:{fixture['source_match_id']}"
        row = session.exec(select(FootballMatchEvent).where(FootballMatchEvent.match_key == match_key)).first()
        if row is None:
            session.add(FootballMatchEvent(match_key=match_key, source_name=source.code, **fixture))
            inserted += 1
            continue
        changed = any(getattr(row, field) != value for field, value in fixture.items())
        if not changed:
            skipped += 1
            continue
        for field, value in fixture.items():
            setattr(row, field, value)
        row.updated_at = datetime.now(UTC)
        session.add(row)
        updated += 1
    return {"received": len(fixtures), "inserted": inserted, "updated": updated, "skipped": skipped}
