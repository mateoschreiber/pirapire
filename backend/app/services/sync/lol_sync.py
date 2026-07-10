"""Manual LoL synchronization (Riot Data Dragon static data)."""

from datetime import UTC, datetime, timedelta

import hashlib
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from sqlmodel import Session, select

from ...config import settings
from ...models_lol import LolChampion, LolGameHistory, LolPatch, LolPlayerGameStat, LolTeamGameStat
from ...models_sources import SourceRun
from ...sources.lol.datadragon import RiotDataDragonClient
from .. import raw_snapshots, source_runs
from ..lol_league_catalog import canonical_league


def _upsert_patch(session, version, source_name, rank):
    existing = session.exec(
        select(LolPatch).where(
            LolPatch.source_name == source_name, LolPatch.version == version
        )
    ).first()
    if existing is not None:
        return (0, 0, 1)
    session.add(
        LolPatch(source_name=source_name, version=version, source_rank=rank, fallback_used=False)
    )
    session.commit()
    return (1, 0, 0)


def _upsert_champion(session, champ, source_name, rank, fallback):
    existing = session.exec(
        select(LolChampion).where(
            LolChampion.source_name == source_name,
            LolChampion.champion_id == champ["champion_id"],
        )
    ).first()
    if existing is not None:
        existing.champion_key = champ.get("champion_key")
        existing.name = champ.get("name") or existing.name
        existing.title = champ.get("title")
        existing.version = champ.get("version")
        existing.source_rank = rank
        existing.fallback_used = fallback
        existing.retrieved_at = datetime.now(UTC)
        session.add(existing)
        session.commit()
        return (0, 1, 0)
    session.add(
        LolChampion(
            source_name=source_name,
            champion_id=champ["champion_id"],
            champion_key=champ.get("champion_key"),
            name=champ.get("name") or champ["champion_id"],
            title=champ.get("title"),
            version=champ.get("version"),
            source_rank=rank,
            fallback_used=fallback,
        )
    )
    session.commit()
    return (1, 0, 0)


def _parse_leaguepedia_datetime(value):
    if not value:
        return None
    text = str(value).replace('T', ' ').replace('Z', '').strip()
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(text[:19], fmt).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _leaguepedia_rows():
    today = datetime.now(UTC)
    start = (today - timedelta(days=settings.leaguepedia_import_lookback_days)).strftime('%Y-%m-%d %H:%M:%S')
    end = (today + timedelta(days=settings.leaguepedia_import_lookahead_days)).strftime('%Y-%m-%d %H:%M:%S')
    quote = chr(34)
    where = 'SG.DateTime_UTC >= ' + quote + start + quote + ' AND SG.DateTime_UTC <= ' + quote + end + quote
    params = {
        'tables': 'ScoreboardGames=SG,Tournaments=T',
        'join_on': 'SG.Tournament=T.OverviewPage',
        'fields': 'SG.DateTime_UTC,SG.Team1,SG.Team2,SG.Winner,T.Name,T.League,SG.OverviewPage',
        'where': where,
        'format': 'json',
        'limit': '500',
    }
    url = settings.leaguepedia_base_url + '?' + urlencode(params)
    req = Request(url, headers={'User-Agent': settings.leaguepedia_user_agent})
    with urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode('utf-8')), url


def _row_id(row):
    payload = '|'.join([
        str(row.get('DateTime UTC') or ''),
        str(row.get('Team1') or ''),
        str(row.get('Team2') or ''),
        str(row.get('OverviewPage') or ''),
    ])
    return hashlib.sha1(payload.encode()).hexdigest()[:24]


def _upsert_leaguepedia_game(session, row):
    team1 = (row.get('Team1') or '').strip()
    team2 = (row.get('Team2') or '').strip()
    winner = str(row.get('Winner') or '').strip()
    dt = _parse_leaguepedia_datetime(row.get('DateTime UTC'))
    if not team1 or not team2 or winner not in ('1', '2') or dt is None:
        return (0, 0, 1)
    if dt > datetime.now(UTC):
        return (0, 0, 1)
    league_raw = row.get('League') or row.get('Name') or row.get('OverviewPage')
    league = canonical_league(league_raw) or league_raw
    gid = _row_id(row)
    winner_team = team1 if winner == '1' else team2
    existing = session.exec(
        select(LolGameHistory).where(
            LolGameHistory.source_name == 'leaguepedia',
            LolGameHistory.source_game_id == gid,
        )
    ).first()
    is_new = existing is None
    game = existing or LolGameHistory(source_name='leaguepedia', source_game_id=gid, source_key=gid)
    game.year = dt.year
    game.league = league
    game.date = dt.isoformat()
    game.blue_team = team1
    game.red_team = team2
    game.winner_team = winner_team
    game.updated_at = datetime.now(UTC)
    session.add(game)
    session.commit()
    session.refresh(game)

    changed = 1 if is_new else 0
    updated = 0 if is_new else 1
    for team, opponent in ((team1, team2), (team2, team1)):
        stat = session.exec(
            select(LolTeamGameStat).where(
                LolTeamGameStat.source_name == 'leaguepedia',
                LolTeamGameStat.source_game_id == gid,
                LolTeamGameStat.team_name == team,
            )
        ).first()
        stat_new = stat is None
        stat = stat or LolTeamGameStat(
            game_id=game.id,
            source_name='leaguepedia',
            source_game_id=gid,
            team_name=team,
            source_key=gid + ':' + team,
        )
        stat.game_id = game.id
        stat.year = dt.year
        stat.league = league
        stat.date = dt.isoformat()
        stat.team_name = team
        stat.opponent_name = opponent
        stat.result = 1 if team == winner_team else 0
        session.add(stat)
        if stat_new:
            changed += 1
        else:
            updated += 1
    session.commit()
    return (changed, updated, 0)




def _leaguepedia_player_rows_with_offset(offset=0):
    """Query ScoreboardPlayers from Leaguepedia Cargo."""
    today = datetime.now(UTC)
    start = (today - timedelta(days=settings.leaguepedia_import_lookback_days)).strftime('%Y-%m-%d %H:%M:%S')
    end = (today + timedelta(days=settings.leaguepedia_import_lookahead_days)).strftime('%Y-%m-%d %H:%M:%S')
    quote = chr(34)
    where = 'SG.DateTime_UTC >= ' + quote + start + quote + ' AND SG.DateTime_UTC <= ' + quote + end + quote
    params = {
        'tables': 'ScoreboardPlayers=SP,ScoreboardGames=SG',
        'join_on': 'SP.GameId=SG.GameId',
        'fields': 'SP.Name,SP.Team,SP.Role,SP.Champion,SP.Kills,SP.Deaths,SP.Assists,SP.CS,SP.Gold,SP.DamageToChampions,SG.DateTime_UTC,SG.Team1,SG.Team2,SG.Winner,SG.OverviewPage,SG.GameId',
        'where': where,
        'format': 'json',
        'limit': '500',
    }
    url = settings.leaguepedia_base_url + '?' + urlencode(params)
    req = Request(url, headers={'User-Agent': settings.leaguepedia_user_agent})
    with urlopen(req, timeout=20) as res:
        return json.loads(res.read().decode('utf-8')), url


def _safe_str(val):
    if val is None:
        return ''
    if isinstance(val, (int, float)):
        return str(val)
    return str(val).strip()


def _safe_int(val):
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if isinstance(val, float):
        return int(val)
    try:
        return int(str(val).strip())
    except (ValueError, TypeError):
        return None


def _upsert_leaguepedia_player(session, row):
    """Import a ScoreboardPlayers row into LolPlayerGameStat."""
    player_name = _safe_str(row.get('Name'))
    team_name = _safe_str(row.get('Team'))
    role = _safe_str(row.get('Role')).lower()
    champion = _safe_str(row.get('Champion'))
    game_id = _safe_str(row.get('GameId'))
    dt = _parse_leaguepedia_datetime(row.get('DateTime UTC'))

    if not player_name or not team_name or not game_id or player_name == '0':
        return (0, 0, 1)

    league_raw = row.get('OverviewPage') or ''
    league = canonical_league(league_raw) or league_raw

    source_key = 'leaguepedia|' + game_id + '|' + player_name + '|' + role

    existing = session.exec(
        select(LolPlayerGameStat).where(LolPlayerGameStat.source_key == source_key)
    ).first()
    if existing:
        return (0, 1, 0)

    kills = _safe_int(row.get('Kills'))
    deaths = _safe_int(row.get('Deaths'))
    assists = _safe_int(row.get('Assists'))
    cs = _safe_int(row.get('CS'))
    gold = _safe_int(row.get('Gold'))
    damage = _safe_int(row.get('DamageToChampions'))

    session.add(LolPlayerGameStat(
        source_name='leaguepedia',
        source_game_id=game_id,
        year=dt.year if dt else None,
        league=league,
        date=dt.isoformat() if dt else None,
        team_name=team_name,
        player_name=player_name,
        role=role,
        champion=champion,
        kills=kills,
        deaths=deaths,
        assists=assists,
        cs=cs,
        gold=gold,
        damage=damage,
        source_key=source_key,
    ))
    return (1, 0, 0)


def _run_leaguepedia_players(session, run: SourceRun):
    """Import players from Leaguepedia ScoreboardPlayers."""
    if not settings.leaguepedia_sync_enabled:
        return (0, 0, 0)
    try:
        rows, url = _leaguepedia_player_rows(0)
    except Exception as exc:
        source_runs.log(session, run, 'warning', f'leaguepedia players cargo failed: {type(exc).__name__}: {exc}')
        return (0, 0, 0)

    raw_snapshots.save_snapshot(session, run.id, 'leaguepedia', 'lol', 'scoreboard_players', rows, external_id='recent-window')
    inserted = updated = skipped = 0
    all_rows = list(rows)
    page = 0
    while len(rows) >= 500:
        page += 1
        try:
            next_rows, _ = _leaguepedia_player_rows_with_offset(page * 500)
            all_rows.extend(next_rows)
            rows = next_rows
        except Exception:
            break
    for row in all_rows:
        i, u, s = _upsert_leaguepedia_player(session, row)
        inserted += i
        updated += u
        skipped += s
        if inserted % 100 == 0:
            session.commit()

    session.commit()
    source_runs.log(session, run, 'info', f'leaguepedia players rows={len(rows)} inserted={inserted} updated={updated} skipped={skipped}')
    return inserted, updated, skipped


def _run_leaguepedia(session, run: SourceRun):
    if not settings.leaguepedia_sync_enabled:
        return (0, 0, 0)
    try:
        rows, url = _leaguepedia_rows()
    except Exception as exc:
        source_runs.log(session, run, 'warning', f'leaguepedia cargo failed: {type(exc).__name__}: {exc}')
        return (0, 0, 0)
    raw_snapshots.save_snapshot(session, run.id, 'leaguepedia', 'lol', 'scoreboard_games', rows, external_id='recent-window')
    inserted = updated = skipped = 0
    for row in rows:
        i, u, s = _upsert_leaguepedia_game(session, row)
        inserted += i
        updated += u
        skipped += s
    source_runs.log(session, run, 'info', f'leaguepedia scoreboard rows={len(rows)} inserted={inserted} updated={updated} skipped={skipped}')
    pi, pu, ps = _run_leaguepedia_players(session, run)
    inserted += pi
    updated += pu
    skipped += ps
    return inserted, updated, skipped


def sync(session: Session, run: SourceRun, only_slug: str | None = None) -> dict:
    inserted = updated = skipped = 0
    client = RiotDataDragonClient(settings.datadragon_base_url, settings.datadragon_locale)

    versions_resp = client.get_versions()
    if not versions_resp["ok"] or not versions_resp["data"]:
        source_runs.log(session, run, "error", f"versions.json: {versions_resp.get('error')}")
        return {"inserted": 0, "updated": 0, "skipped": 0, "status": "error"}

    versions = versions_resp["data"]
    raw_snapshots.save_snapshot(
        session, run.id, client.slug, "lol", "versions", versions, external_id="versions"
    )
    latest = client.latest_version(versions)
    source_runs.log(session, run, "info", f"latest Data Dragon version: {latest}")
    i, u, s = _upsert_patch(session, latest, client.slug, client.rank)
    inserted += i
    updated += u
    skipped += s

    used_locale = settings.datadragon_locale
    fallback_locale = False
    champ_resp = client.get_champions(latest, used_locale)
    if not champ_resp["ok"] or not champ_resp["data"]:
        source_runs.log(
            session, run, "warning", f"champion.json {used_locale} failed; retrying en_US"
        )
        used_locale = "en_US"
        fallback_locale = True
        champ_resp = client.get_champions(latest, used_locale)

    if champ_resp["ok"] and champ_resp["data"]:
        raw_snapshots.save_snapshot(
            session, run.id, client.slug, "lol", "champion", champ_resp["data"],
            external_id=f"champion-{used_locale}",
        )
        champions = client.normalize_champions(champ_resp["data"], latest)
        for champ in champions:
            i, u, s = _upsert_champion(session, champ, client.slug, client.rank, fallback_locale)
            inserted += i
            updated += u
            skipped += s
        source_runs.log(session, run, "info", f"{len(champions)} champions ({used_locale})")
    else:
        source_runs.log(session, run, "error", "champion.json failed on both locales")

    i, u, s = _run_leaguepedia(session, run)
    inserted += i
    updated += u
    skipped += s

    status = source_runs.resolve_status(inserted, updated, skipped, run.error_count or 0)
    return {"inserted": inserted, "updated": updated, "skipped": skipped, "status": status}
