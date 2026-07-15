import os, csv, hashlib
from datetime import datetime, timezone
from sqlmodel import Session, select
from ..models_lol import LolGameHistory, LolTeamGameStat, LolPlayerGameStat, LolSeries, LolDataCoverage
from .lol_team_aliases import resolve_team_alias


def _now():
    return datetime.now(timezone.utc)


def import_oracles_inbox(session: Session):
    from ..config import settings
    inbox = os.path.join(settings.lol_history_import_dir, "inbox")
    processed = os.path.join(settings.lol_history_import_dir, "processed")
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(processed, exist_ok=True)
    total_games = 0
    if not os.path.isdir(inbox):
        return {"inserted": 0}
    for fname in os.listdir(inbox):
        if not fname.endswith(".csv"):
            continue
        fpath = os.path.join(inbox, fname)
        count = _import_oracles_csv(session, fpath)
        total_games += count
        os.rename(fpath, os.path.join(processed, fname))
    return {"inserted": total_games}


def _import_oracles_csv(session: Session, filepath: str):
    inserted = 0
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                if _upsert_oracles_row(session, row):
                    inserted += 1
            except Exception:
                continue
        session.commit()
    return inserted


def _upsert_oracles_row(session: Session, row):
    gameid = (row.get("gameid") or row.get("game_id") or "").strip()
    if not gameid:
        return False
    source_key = f"oracles_elixir:{gameid}"
    existing = session.exec(select(LolGameHistory).where(LolGameHistory.source_key == source_key)).first()
    if existing:
        return False

    date = (row.get("date") or "").strip()
    league = (row.get("league") or "").strip()
    patch = (row.get("patch") or "").strip()
    side = (row.get("side") or "").strip().lower()
    position = (row.get("position") or "").strip().lower()
    team = (row.get("teamname") or row.get("team") or "").strip()
    opponent = (row.get("opponent") or "").strip()
    player = (row.get("playername") or row.get("player") or "").strip()
    champion = (row.get("champion") or "").strip()

    def _int(val):
        try: return int(float(val))
        except: return None

    kills = _int(row.get("kills", 0))
    deaths = _int(row.get("deaths", 0))
    assists = _int(row.get("assists", 0))
    team_kills = _int(row.get("teamkills", row.get("team_kills", 0)))
    team_deaths = _int(row.get("teamdeaths", row.get("team_deaths", 0)))
    dragons = _int(row.get("dragons", row.get("elementaldrakes", 0)))
    barons = _int(row.get("barons", 0))
    towers = _int(row.get("towers", 0))
    inhibitors = _int(row.get("inhibitors", 0))
    cs = _int(row.get("totalcs", row.get("cs", 0)))
    gold = _int(row.get("totalgold", row.get("gold", 0)))
    game_length = _int(row.get("gamelength", row.get("game_length", 0)))
    result = 1 if int(float(row.get("result", 0))) == 1 else 0
    side = "blue" if side == "blue" else "red"

    game = LolGameHistory(
        source_name="oracles_elixir",
        source_game_id=gameid,
        source_key=source_key,
        year=int(date[:4]) if len(date) >= 4 else None,
        league=league,
        date=date,
        patch=patch,
        game_length_seconds=game_length,
        blue_team=team if side == "blue" else opponent,
        red_team=team if side == "red" else opponent,
    )
    session.add(game)
    session.commit()
    session.refresh(game)

    stat = LolTeamGameStat(
        game_id=game.id,
        source_name="oracles_elixir",
        source_game_id=gameid,
        source_key=f"{source_key}:{team}",
        year=game.year,
        league=league,
        date=date,
        patch=patch,
        team_name=team,
        opponent_name=opponent,
        side=side,
        result=result,
        kills=kills,
        deaths=deaths,
        assists=assists,
        team_kills=team_kills,
        team_deaths=team_deaths,
        dragons=dragons,
        barons=barons,
        towers=towers,
        inhibitors=inhibitors,
        game_length_seconds=game_length,
        gold=gold,
    )
    session.add(stat)

    if player:
        pstat = LolPlayerGameStat(
            game_id=game.id,
            source_name="oracles_elixir",
            source_game_id=gameid,
            source_key=f"{source_key}:{player}",
            year=game.year,
            league=league,
            date=date,
            patch=patch,
            team_name=team,
            player_name=player,
            role=position,
            champion=champion,
            kills=kills,
            deaths=deaths,
            assists=assists,
            cs=cs,
            gold=gold,
            solo_kills=_int(row.get("solokills", None)),
        )
        session.add(pstat)

    return True
