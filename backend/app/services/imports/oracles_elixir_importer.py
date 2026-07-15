import csv
import logging
import os

from sqlalchemy import delete
from sqlmodel import Session, select

from ...models_lol import LolDataCoverage, LolGameHistory, LolPlayerGameStat, LolTeamGameStat

log = logging.getLogger(__name__)


def _int(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _bool(value):
    parsed = _int(value)
    return bool(parsed) if parsed is not None else None


def _normalized_row(row):
    return {
        str(key).strip().lower().replace(" ", "").replace("_", ""): value
        for key, value in row.items() if key is not None
    }


def import_oracles_inbox(session: Session):
    from ...config import settings

    inbox = os.path.join(settings.lol_history_import_dir, "inbox")
    processed = os.path.join(settings.lol_history_import_dir, "processed")
    errors = os.path.join(settings.lol_history_import_dir, "errors")
    for directory in (inbox, processed, errors):
        os.makedirs(directory, exist_ok=True)
    total = {"games": 0, "teams": 0, "players": 0}
    for filename in sorted(os.listdir(inbox)):
        if not filename.endswith(".csv"):
            continue
        source = os.path.join(inbox, filename)
        try:
            result = _import_csv_file(session, source)
            for key in total:
                total[key] += result[key]
            destination = os.path.join(processed, filename)
        except Exception as exc:
            log.exception("Failed import %s: %s", filename, exc)
            destination = os.path.join(errors, filename)
        os.replace(source, destination)
    return total


def _import_csv_file(session: Session, filepath: str, replace: bool = False):
    """Import an OE CSV; replacement mode is atomic and removes stale maps for its years."""
    from itertools import groupby

    result = {"games": 0, "teams": 0, "players": 0}
    seen_gameids = set()
    years = set()
    try:
        with open(filepath, newline="", encoding="utf-8-sig") as source:
            raw_reader = csv.DictReader(source)
            required = {"gameid", "position", "teamname"}
            normalized_headers = {
                str(name).strip().lower().replace(" ", "").replace("_", "")
                for name in (raw_reader.fieldnames or [])
            }
            if not required.issubset(normalized_headers):
                missing = sorted(required - normalized_headers)
                raise ValueError(f"Missing required columns: {', '.join(missing)}")
            reader = (_normalized_row(row) for row in raw_reader)

            def game_key(row):
                return (row.get("gameid") or "").strip()

            processed_groups = 0
            for gameid, grouped_rows in groupby(reader, key=game_key):
                if not gameid:
                    continue
                game_rows = list(grouped_rows)
                date = (game_rows[0].get("date") or "").strip() if game_rows else ""
                if len(date) >= 4 and date[:4].isdigit():
                    years.add(int(date[:4]))
                seen_gameids.add(gameid)
                imported = _process_game(session, gameid, game_rows, replace=replace)
                for key in result:
                    result[key] += imported[key]
                processed_groups += 1
                if not replace and processed_groups % 250 == 0:
                    session.commit()

        if replace:
            if not years:
                raise ValueError("No se detectó un año válido para reemplazar")
            existing = session.exec(
                select(LolGameHistory).where(
                    LolGameHistory.source_name == "oracles_elixir",
                    LolGameHistory.year.in_(years),
                )
            ).all()
            stale_ids = [game.id for game in existing if game.source_game_id not in seen_gameids]
            for offset in range(0, len(stale_ids), 500):
                chunk = stale_ids[offset:offset + 500]
                session.exec(delete(LolPlayerGameStat).where(LolPlayerGameStat.game_id.in_(chunk)))
                session.exec(delete(LolTeamGameStat).where(LolTeamGameStat.game_id.in_(chunk)))
                session.exec(delete(LolGameHistory).where(LolGameHistory.id.in_(chunk)))
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise


def _process_game(session: Session, gameid: str, rows: list[dict], replace: bool = False):
    source_key = f"oracles_elixir:{gameid}"
    existing = session.exec(select(LolGameHistory).where(LolGameHistory.source_key == source_key)).first()
    if existing and not replace:
        return {"games": 0, "teams": 0, "players": 0}

    team_rows, player_rows = [], []
    for row in rows:
        position = (row.get("position") or row.get("participantid") or "").strip().lower()
        (team_rows if position in ("", "team", "total", "0") else player_rows).append(row)
    if not team_rows:
        return {"games": 0, "teams": 0, "players": 0}

    first = team_rows[0]
    date = (first.get("date") or "").strip()
    league = (first.get("league") or "").strip()
    patch = (first.get("patch") or "").strip()
    game_length = _int(first.get("gamelength", first.get("gamelengthseconds")))
    blue_team = red_team = None
    team_stats_by_side = {}
    for row in team_rows:
        side = "blue" if "blue" in (row.get("side") or "").strip().lower() else "red"
        team_name = (row.get("teamname") or row.get("team") or "").strip()
        if not team_name:
            continue
        if side == "blue":
            blue_team = team_name
        else:
            red_team = team_name
        team_stats_by_side[side] = row
    blue_team = blue_team or (team_stats_by_side.get("blue", {}).get("teamname") or "")
    red_team = red_team or (team_stats_by_side.get("red", {}).get("teamname") or "")

    if existing:
        session.exec(delete(LolPlayerGameStat).where(LolPlayerGameStat.game_id == existing.id))
        session.exec(delete(LolTeamGameStat).where(LolTeamGameStat.game_id == existing.id))
        game = existing
    else:
        game = LolGameHistory(source_name="oracles_elixir", source_game_id=gameid, source_key=source_key)
    game.year = int(date[:4]) if len(date) >= 4 and date[:4].isdigit() else None
    game.league = league
    game.split = (first.get("split") or "").strip() or None
    game.playoffs = _bool(first.get("playoffs"))
    game.date = date
    game.patch = patch
    game.game_number = _int(first.get("game"))
    game.game_length_seconds = game_length
    game.blue_team = blue_team
    game.red_team = red_team
    game.winner_team = next(((row.get("teamname") or "").strip() for row in team_rows if _int(row.get("result")) == 1), None)
    session.add(game)
    session.flush()

    teams_added = 0
    for side, row in team_stats_by_side.items():
        team_name = (row.get("teamname") or row.get("team") or "").strip()
        if not team_name:
            continue
        stat = LolTeamGameStat(
            game_id=game.id, source_name="oracles_elixir", source_game_id=gameid,
            source_key=f"{source_key}:{team_name}", year=game.year, league=league, date=date, patch=patch,
            team_name=team_name, opponent_name=blue_team if side == "red" else red_team, side=side,
            result=_int(row.get("result")), kills=_int(row.get("kills")), deaths=_int(row.get("deaths")),
            assists=_int(row.get("assists")), team_kills=_int(row.get("teamkills")),
            team_deaths=_int(row.get("teamdeaths")), dragons=_int(row.get("dragons", row.get("elementaldrakes"))),
            barons=_int(row.get("barons")), towers=_int(row.get("towers")), inhibitors=_int(row.get("inhibitors")),
            game_length_seconds=game_length, first_blood=_bool(row.get("firstblood")), first_tower=_bool(row.get("firsttower")),
            gold=_int(row.get("totalgold", row.get("gold"))), final_gold=_int(row.get("totalgold", row.get("gold"))),
            earned_gold=_int(row.get("earnedgold")),
        )
        session.add(stat)
        teams_added += 1

    players_added = 0
    for row in player_rows:
        player_name = (row.get("playername") or row.get("player") or "").strip()
        if not player_name:
            continue
        session.add(LolPlayerGameStat(
            game_id=game.id, source_name="oracles_elixir", source_game_id=gameid,
            source_key=f"{source_key}:{player_name}", year=game.year, league=league, date=date, patch=patch,
            team_name=(row.get("teamname") or row.get("team") or "").strip(), player_name=player_name,
            role=(row.get("position") or row.get("role") or "").strip(), champion=(row.get("champion") or "").strip(),
            kills=_int(row.get("kills")), deaths=_int(row.get("deaths")), assists=_int(row.get("assists")),
            cs=_int(row.get("totalcs", row.get("cs"))), damage=_int(row.get("damagetochampions")),
            gold=_int(row.get("totalgold", row.get("gold"))), final_gold=_int(row.get("totalgold", row.get("gold"))),
            solo_kills=_int(row.get("solokills")),
        ))
        players_added += 1
    return {"games": 1, "teams": teams_added, "players": players_added}
