"""Import historical LoL esports CSV (Oracle's Elixir format) into canonical tables.

Team rows become LolTeamGameStat; player rows become LolPlayerGameStat.
Missing columns are tolerated; unknown columns are warned.
"""

from sqlmodel import Session

from . import csv_utils
from ...models_imports import ManualImportBatch
from ...models_lol import LolTeamGameStat, LolPlayerGameStat

KNOWN_COLUMNS = {
    "gameid", "datacompleteness", "url", "league", "year", "split", "playoffs",
    "date", "game", "patch", "participantid", "side", "position", "playername",
    "playerid", "teamname", "teamid", "champion", "ban1", "ban2", "ban3", "ban4",
    "ban5", "gamelength", "result", "kills", "deaths", "assists", "teamkills",
    "teamdeaths", "doublekills", "triplekills", "quadrakills", "pentakills",
    "firstblood", "firstbloodkill", "firstbloodassist", "firstbloodvictim",
    "team kpm", "ckpm", "firstdragon", "dragons", "opp_dragons", "elementaldrakes",
    "opp_elementaldrakes", "infernals", "mountains", "clouds", "oceans", "chemtechs",
    "hextechs", "dragons_type_unknown", "elders", "opp_elders", "firstherald",
    "heralds", "opp_heralds", "void_grubs", "opp_void_grubs", "firstbaron", "barons",
    "opp_barons", "firsttower", "towers", "opp_towers", "firstmidtower",
    "firsttothreetowers", "inhibitors", "opp_inhibitors", "damagetochampions", "dpm",
    "damageshare", "earnedgold", "earned gpm", "earnedgoldshare", "total cs",
    "minionkills", "monsterkills", "cspm",
}


def _total_cs(row: dict) -> int | None:
    total = csv_utils.safe_int(csv_utils.col(row, "total cs"))
    if total is not None:
        return total
    minions = csv_utils.safe_int(csv_utils.col(row, "minionkills")) or 0
    monsters = csv_utils.safe_int(csv_utils.col(row, "monsterkills")) or 0
    combined = minions + monsters
    return combined or None


def import_csv(session: Session, batch: ManualImportBatch, csv_text: str) -> ManualImportBatch:
    try:
        rows = csv_utils.read_rows(csv_text)
    except Exception as exc:
        return csv_utils.finish_batch(session, batch, "error", f"failed to parse CSV: {exc}")

    team_rows = 0
    player_rows = 0
    skipped = 0
    seen: set = set()
    warned_unknown = False

    for i, row in enumerate(rows, start=2):
        try:
            gameid = (csv_utils.col(row, "gameid") or "").strip()
            if not gameid:
                csv_utils.log_import_error(session, batch, i, "missing gameid", row, "error")
                continue
            position = (csv_utils.col(row, "position") or "").strip().lower()
            teamname = (csv_utils.col(row, "teamname") or "").strip()

            if not warned_unknown:
                unknown = [k for k in row if k and k.strip().lower() not in KNOWN_COLUMNS]
                if unknown:
                    warned_unknown = True
                    csv_utils.log_import_error(
                        session, batch, i, f"unrecognized columns ignored: {unknown[:10]}", None, "warning"
                    )

            if position == "team":
                key = ("team", gameid, teamname)
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)

                source_key = f"oracles_elixir|{gameid}|{teamname}"
                session.add(
                    LolTeamGameStat(
                        source_name="oracles_elixir",
                        source_game_id=gameid,
                        source_key=source_key,
                        date=csv_utils.col(row, "date"),
                        league=csv_utils.col(row, "league"),
                        patch=csv_utils.col(row, "patch"),
                        team_name=teamname or "?",
                        side=csv_utils.col(row, "side"),
                        result=csv_utils.safe_int(csv_utils.col(row, "result")),
                        kills=csv_utils.safe_int(csv_utils.col(row, "teamkills")),
                        deaths=csv_utils.safe_int(csv_utils.col(row, "teamdeaths")),
                        towers=csv_utils.safe_int(csv_utils.col(row, "towers")),
                        inhibitors=csv_utils.safe_int(csv_utils.col(row, "inhibitors")),
                        dragons=csv_utils.safe_int(csv_utils.col(row, "dragons")),
                        barons=csv_utils.safe_int(csv_utils.col(row, "barons")),
                        gold=csv_utils.safe_int(csv_utils.col(row, "earnedgold")),
                        game_length_seconds=csv_utils.parse_game_length_seconds(csv_utils.col(row, "gamelength")),
                    )
                )
                team_rows += 1
            else:
                playername = (csv_utils.col(row, "playername") or "").strip()
                key = ("player", gameid, playername, position)
                if key in seen:
                    skipped += 1
                    continue
                seen.add(key)

                source_key = f"oracles_elixir|{gameid}|{playername}|{position}"
                session.add(
                    LolPlayerGameStat(
                        source_name="oracles_elixir",
                        source_game_id=gameid,
                        source_key=source_key,
                        date=csv_utils.col(row, "date"),
                        league=csv_utils.col(row, "league"),
                        team_name=teamname or None,
                        player_name=playername or None,
                        role=position or None,
                        champion=csv_utils.col(row, "champion"),
                        kills=csv_utils.safe_int(csv_utils.col(row, "kills")),
                        deaths=csv_utils.safe_int(csv_utils.col(row, "deaths")),
                        assists=csv_utils.safe_int(csv_utils.col(row, "assists")),
                        cs=_total_cs(row),
                        gold=csv_utils.safe_int(csv_utils.col(row, "earnedgold")),
                        damage=csv_utils.safe_int(csv_utils.col(row, "damagetochampions")),
                    )
                )
                player_rows += 1
            session.commit()
        except Exception as exc:
            csv_utils.log_import_error(session, batch, i, f"row parse error: {exc}", row, "error")

    batch.imported_rows = team_rows + player_rows
    batch.skipped_rows = skipped
    status = "success" if batch.error_rows == 0 else ("partial" if batch.imported_rows > 0 else "error")
    message = f"team_rows={team_rows} player_rows={player_rows} (canonical tables)"
    return csv_utils.finish_batch(session, batch, status, message)
