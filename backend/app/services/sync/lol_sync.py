from datetime import UTC, datetime, timedelta
import hashlib, json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from sqlmodel import Session, select
from ...config import settings
from ...models_lol import LolMatchEvent, LolChampion, LolPatch
from ...sources.lol.datadragon import RiotDataDragonClient
from ..lol_league_catalog import canonical_league


def _upsert_patch(session, version, source_name, rank):
    existing = session.exec(select(LolPatch).where(LolPatch.source_name == source_name, LolPatch.version == version)).first()
    if existing:
        return (0, 0, 1)
    session.add(LolPatch(source_name=source_name, version=version, source_rank=rank, fallback_used=False))
    session.commit()
    return (1, 0, 0)


def _upsert_champion(session, champ, source_name, rank, fallback):
    existing = session.exec(select(LolChampion).where(LolChampion.source_name == source_name, LolChampion.champion_id == champ["champion_id"])).first()
    if existing:
        existing.champion_key = champ.get("champion_key")
        existing.name = champ.get("name") or existing.name
        existing.title = champ.get("title")
        existing.version = champ.get("version")
        existing.source_rank = rank
        existing.fallback_used = fallback
        existing.retrieved_at = datetime.now(UTC)
        session.add(existing); session.commit()
        return (0, 1, 0)
    session.add(LolChampion(source_name=source_name, champion_id=champ["champion_id"], champion_key=champ.get("champion_key"), name=champ.get("name") or champ["champion_id"], title=champ.get("title"), version=champ.get("version"), source_rank=rank, fallback_used=fallback))
    session.commit()
    return (1, 0, 0)


def _parse_datetime(value):
    if not value: return None
    text = str(value).replace("T", " ").replace("Z", "").strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try: return datetime.strptime(text[:19], fmt).replace(tzinfo=UTC)
        except ValueError: continue
    return None


def _make_match_key(source_name, source_match_id):
    raw = f"{source_name}:{source_match_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _fetch_match_schedule(offset=0):
    now = datetime.now(UTC)
    start = (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S")
    end = (now + timedelta(days=settings.leaguepedia_import_lookahead_days)).strftime("%Y-%m-%d %H:%M:%S")
    q = '"'
    where = f"DateTime_UTC >= {q}{start}{q} AND DateTime_UTC <= {q}{end}{q}"
    params = {
        "tables": "MatchSchedule",
        "fields": "Team1,Team2,DateTime_UTC,MatchId,BestOf,Winner,OverviewPage",
        "where": where,
        "format": "json",
        "limit": "500",
        "order_by": "DateTime_UTC ASC",
        "offset": str(offset),
    }
    url = settings.leaguepedia_base_url + "?" + urlencode(params)
    req = Request(url, headers={"User-Agent": settings.leaguepedia_user_agent})
    with urlopen(req, timeout=30) as res:
        return json.loads(res.read().decode("utf-8"))


def _fetch_all_pages():
    all_rows = []
    offset = 0
    while True:
        page = _fetch_match_schedule(offset)
        if not page:
            break
        all_rows.extend(page)
        if len(page) < 500:
            break
        offset += 500
    return all_rows


def _upsert_match_event(session, row):
    team1 = (row.get("Team1") or "").strip()
    team2 = (row.get("Team2") or "").strip()
    dt = _parse_datetime(row.get("DateTime UTC"))
    winner_raw = str(row.get("Winner") or "").strip()

    if not team1 or not team2 or dt is None:
        return (0, 0, 1)
    if team1 == "TBD" and team2 == "TBD":
        return (0, 0, 1)

    match_id = row.get("MatchId") or ""
    if match_id:
        source_match_id = match_id
    else:
        source_match_id = f"{dt.isoformat()}|{team1}|{team2}"
    match_key = _make_match_key("leaguepedia", source_match_id)

    now = datetime.now(UTC)
    has_winner = winner_raw in ("1", "2")
    if dt > now and not has_winner:
        status = "scheduled"
    elif dt > now and has_winner:
        status = "live"
    elif has_winner:
        status = "finished"
    else:
        status = "scheduled"

    overview = row.get("OverviewPage") or ""
    tournament = overview
    league = canonical_league(overview) or overview

    existing = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
    is_new = existing is None
    match = existing or LolMatchEvent(match_key=match_key, source_name="leaguepedia", source_match_id=source_match_id)

    best_of_raw = row.get("BestOf")
    try: best_of = int(best_of_raw) if best_of_raw else None
    except: best_of = None

    source_url = f"https://lol.fandom.com/wiki/{overview.replace(' ', '_')}" if overview else ""
    current_start = match.start_time_utc
    if current_start and current_start.tzinfo is None:
        current_start = current_start.replace(tzinfo=UTC)
    changed = is_new or current_start != dt or any(
        getattr(match, field) != value
        for field, value in {
            "league": league,
            "tournament": tournament,
            "team_a": team1,
            "team_b": team2,
            "best_of": best_of,
            "status": status,
            "source_url": source_url,
        }.items()
    )
    if not changed:
        return (0, 0, 1)
    match.league = league
    match.tournament = tournament
    match.team_a = team1
    match.team_b = team2
    match.start_time_utc = dt
    match.best_of = best_of
    match.status = status
    match.source_url = source_url
    match.observed_at = now
    match.updated_at = now
    session.add(match)
    session.commit()
    return (1 if is_new else 0, 0 if is_new else 1, 0)


def sync_leaguepedia_schedule(session: Session):
    if not settings.leaguepedia_sync_enabled:
        return {"inserted": 0, "updated": 0, "skipped": 0}
    try:
        rows = _fetch_all_pages()
    except Exception as exc:
        return {"error": str(exc), "inserted": 0, "updated": 0, "skipped": 0}

    inserted = updated = skipped = 0
    for row in rows:
        i, u, s = _upsert_match_event(session, row)
        inserted += i; updated += u; skipped += s

    if inserted or updated:
        from ..lol_metrics_engine import invalidate_statistics_cache

        invalidate_statistics_cache(session)
        session.commit()

    scheduled_count = session.exec(select(LolMatchEvent).where(LolMatchEvent.status == "scheduled")).all()
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "total_rows": len(rows), "scheduled": len(scheduled_count)}


def sync_datadragon(session: Session):
    client = RiotDataDragonClient(settings.datadragon_base_url, settings.datadragon_locale)
    versions_resp = client.get_versions()
    if not versions_resp["ok"] or not versions_resp["data"]:
        return {"error": "versions.json failed", "inserted": 0, "updated": 0}

    versions = versions_resp["data"]
    latest = client.latest_version(versions)
    i, u, s = _upsert_patch(session, latest, client.slug, client.rank)
    inserted, updated = i, u

    champ_resp = client.get_champions(latest, settings.datadragon_locale)
    loc = settings.datadragon_locale; fallback = False
    if not champ_resp["ok"] or not champ_resp["data"]:
        loc = "en_US"; fallback = True
        champ_resp = client.get_champions(latest, loc)

    if champ_resp["ok"] and champ_resp["data"]:
        champions = client.normalize_champions(champ_resp["data"], latest or "16.14.1")
        for champ in champions:
            i, u, s = _upsert_champion(session, champ, client.slug, client.rank, fallback)
            inserted += i; updated += u
    return {"inserted": inserted, "updated": updated, "latest_version": latest}
