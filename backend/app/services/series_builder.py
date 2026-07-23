import hashlib
import json
from collections import defaultdict
from datetime import datetime
from sqlalchemy import delete, update
from sqlmodel import Session, select
from ..models_lol import LolGameHistory, LolSeries


def rebuild_series(session: Session):
    from .lol_metrics_engine import invalidate_statistics_cache

    games = session.exec(select(LolGameHistory).order_by(LolGameHistory.date)).all()
    buckets = defaultdict(list)
    for game in games:
        pair = tuple(sorted((game.blue_team or "", game.red_team or "")))
        if not all(pair) or not game.date:
            continue
        day = game.date[:10]
        buckets[(game.league or "", day, pair)].append(game)
    session.exec(update(LolGameHistory).values(series_id=None))
    session.flush()
    session.exec(delete(LolSeries))
    for items in buckets.values():
        items.sort(key=lambda g:g.date or "")
        # Same league/pair/date represents one match; OE game IDs are individual maps.
        first = items[0]; last = items[-1]
        wins = defaultdict(int)
        for g in items:
            if g.winner_team: wins[g.winner_team] += 1
        a,b = first.blue_team, first.red_team
        score_a,score_b=wins[a],wins[b]
        best_of = 1 if len(items)==1 else 3 if len(items)<=3 else 5
        key = hashlib.sha256(f"{first.league}|{first.date[:10]}|{a}|{b}|{first.source_name}".encode()).hexdigest()[:24]
        series = LolSeries(series_key=key,source_name=first.source_name,team_a=a,team_b=b,score_a=score_a,score_b=score_b,
                           league=first.league,best_of=best_of,first_game_at=first.date,last_game_at=last.date,
                           game_ids_json=json.dumps([g.id for g in items]),maps_count=len(items),complete=True)
        session.add(series); session.flush()
        for g in items: g.series_id=series.id; session.add(g)
    invalidate_statistics_cache(session)
    session.commit()
    return len(buckets)
