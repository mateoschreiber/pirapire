import os, csv, hashlib, json, logging
from collections import defaultdict
from datetime import datetime, timezone
from sqlmodel import Session, select
from ...models_lol import LolGameHistory, LolTeamGameStat, LolPlayerGameStat, LolDataCoverage

log = logging.getLogger(__name__)


def _now():
    return datetime.now(timezone.utc)


def _int(val):
    try: return int(float(val))
    except: return None


def _normalize_headers(reader):
    mapping = {}
    for h in reader.fieldnames or []:
        key = h.strip().lower().replace(" ", "").replace("_", "")
        mapping[h] = key
    return mapping


def import_oracles_inbox(session: Session):
    from ...config import settings
    inbox = os.path.join(settings.lol_history_import_dir, "inbox")
    processed = os.path.join(settings.lol_history_import_dir, "processed")
    errors = os.path.join(settings.lol_history_import_dir, "errors")
    for d in (inbox, processed, errors):
        os.makedirs(d, exist_ok=True)

    total = {"games": 0, "teams": 0, "players": 0}
    for fname in sorted(os.listdir(inbox)):
        if not fname.endswith(".csv"):
            continue
        fpath = os.path.join(inbox, fname)
        try:
            result = _import_csv_file(session, fpath)
            total["games"] += result["games"]
            total["teams"] += result["teams"]
            total["players"] += result["players"]
            dst = os.path.join(processed, fname)
        except Exception as e:
            log.exception(f"Failed import {fname}: {e}")
            dst = os.path.join(errors, fname)
        os.rename(fpath, dst)
    return total


def _import_csv_file(session: Session, filepath: str):
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    # Group rows by gameid
    games = defaultdict(list)
    for row in rows:
        gameid = (row.get("gameid") or row.get("game_id") or "").strip()
        if not gameid:
            continue
        games[gameid].append(row)

    result = {"games": 0, "teams": 0, "players": 0}
    for gameid, game_rows in games.items():
        try:
            r = _process_game(session, gameid, game_rows)
            result["games"] += r["games"]
            result["teams"] += r["teams"]
            result["players"] += r["players"]
        except Exception as e:
            log.warning(f"Game {gameid}: {e}")
    session.commit()
    return result


def _process_game(session, gameid, rows):
    source_key = f"oracles_elixir:{gameid}"
    existing = session.exec(select(LolGameHistory).where(LolGameHistory.source_key == source_key)).first()
    if existing:
        return {"games": 0, "teams": 0, "players": 0}

    # Identify team rows vs player rows
    team_rows = []
    player_rows = []
    for row in rows:
        pos = (row.get("position") or row.get("participantid") or "").strip().lower()
        if pos in ("", "team", "total", "0"):
            team_rows.append(row)
        else:
            player_rows.append(row)

    if not team_rows:
        return {"games": 0, "teams": 0, "players": 0}

    # Get game metadata from first team row
    first = team_rows[0]
    date = (first.get("date") or "").strip()
    league = (first.get("league") or "").strip()
    patch = (first.get("patch") or "").strip()
    game_length = _int(first.get("gamelength", first.get("game_length", 0)))

    # Determine teams from team rows (side should be Blue/Red)
    blue_team = red_team = None
    team_stats_by_side = {}
    for tr in team_rows:
        side_raw = (tr.get("side") or "").strip().lower()
        team_name = (tr.get("teamname") or tr.get("team") or "").strip()
        if not team_name:
            continue
        side = "blue" if "blue" in side_raw else "red"
        if side == "blue":
            blue_team = team_name
        else:
            red_team = team_name
        team_stats_by_side[side] = tr

    if not blue_team:
        blue_team = team_stats_by_side.get("blue", {}).get("teamname") or team_stats_by_side.get("blue", {}).get("team") or ""
    if not red_team:
        red_team = team_stats_by_side.get("red", {}).get("teamname") or team_stats_by_side.get("red", {}).get("team") or ""

    # Create game
    game = LolGameHistory(
        source_name="oracles_elixir",
        source_game_id=gameid,
        source_key=source_key,
        year=int(date[:4]) if len(date) >= 4 else None,
        league=league,
        date=date,
        patch=patch,
        game_length_seconds=game_length,
        blue_team=blue_team or "",
        red_team=red_team or "",
    )
    session.add(game)
    session.commit()
    session.refresh(game)

    teams_added = 0
    # Create team stats for each side
    for side, tr in team_stats_by_side.items():
        team_name = (tr.get("teamname") or tr.get("team") or "").strip()
        if not team_name:
            continue
        opp_name = blue_team if side == "red" else red_team
        stat = LolTeamGameStat(
            game_id=game.id,
            source_name="oracles_elixir",
            source_game_id=gameid,
            source_key=f"{source_key}:{team_name}",
            year=game.year,
            league=league,
            date=date,
            patch=patch,
            team_name=team_name,
            opponent_name=opp_name or "",
            side=side,
            result=_int(tr.get("result", 0)),
            kills=_int(tr.get("kills", 0)),
            deaths=_int(tr.get("deaths", 0)),
            assists=_int(tr.get("assists", 0)),
            team_kills=_int(tr.get("teamkills", tr.get("team_kills", 0))),
            team_deaths=_int(tr.get("teamdeaths", tr.get("team_deaths", 0))),
            dragons=_int(tr.get("dragons", tr.get("elementaldrakes", 0))),
            barons=_int(tr.get("barons", 0)),
            towers=_int(tr.get("towers", 0)),
            inhibitors=_int(tr.get("inhibitors", 0)),
            game_length_seconds=game_length,
            gold=_int(tr.get("totalgold", tr.get("gold", 0))),
        )
        session.add(stat)
        teams_added += 1

    players_added = 0
    for pr in player_rows:
        team_name = (pr.get("teamname") or pr.get("team") or "").strip()
        player_name = (pr.get("playername") or pr.get("player") or "").strip()
        if not player_name:
            continue
        pstat = LolPlayerGameStat(
            game_id=game.id,
            source_name="oracles_elixir",
            source_game_id=gameid,
            source_key=f"{source_key}:{player_name}",
            year=game.year,
            league=league,
            date=date,
            patch=patch,
            team_name=team_name,
            player_name=player_name,
            role=(pr.get("position") or pr.get("role") or "").strip(),
            champion=(pr.get("champion") or "").strip(),
            kills=_int(pr.get("kills", 0)),
            deaths=_int(pr.get("deaths", 0)),
            assists=_int(pr.get("assists", 0)),
            cs=_int(pr.get("totalcs", pr.get("cs", 0))),
            gold=_int(pr.get("totalgold", pr.get("gold", 0))),
            solo_kills=_int(pr.get("solokills", None)),
        )
        session.add(pstat)
        players_added += 1

    return {"games": 1, "teams": teams_added, "players": players_added}
