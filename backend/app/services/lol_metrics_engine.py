from statistics import mean

from sqlmodel import Session, select

from ..config import settings
from ..models_lol import LolPlayerGameStat, LolTeamGameStat
from .lol_team_aliases import canonical_team


def avg(values):
    vals = [v for v in values if v is not None]
    return mean(vals) if vals else None


def rate(values):
    vals = [v for v in values if v is not None]
    return (sum(1 for v in vals if v) / len(vals)) if vals else None


def confidence(sample_size: int, minimum: int) -> float:
    if minimum <= 0:
        minimum = 1
    return max(0.05, min(1.0, sample_size / float(minimum * 2)))


def ordered_recent(rows):
    return sorted(rows, key=lambda r: (r.date or '', r.source_game_id or ''), reverse=True)


def team_rows(session: Session, team: str, league: str | None = None, window: int | None = None):
    canonical = canonical_team(session, team, league) or team
    query = select(LolTeamGameStat).where(LolTeamGameStat.team_name == canonical)
    if league:
        query = query.where(LolTeamGameStat.league == league)
    rows = session.exec(query).all()
    rows = ordered_recent(rows)
    return rows[:window] if window else rows


def team_metrics(session: Session, team: str, league: str | None = None, window: int = 20) -> dict:
    rows = team_rows(session, team, league, window)
    sample = len(rows)
    min_games = getattr(settings, 'lol_history_min_games_team', 8)
    return {
        'team': team,
        'league': league,
        'window': window,
        'sample_size': sample,
        'confidence': confidence(sample, min_games),
        'winrate': avg([r.result for r in rows]),
        'avg_kills': avg([r.team_kills if r.team_kills is not None else r.kills for r in rows]),
        'avg_deaths': avg([r.team_deaths if r.team_deaths is not None else r.deaths for r in rows]),
        'avg_total_kills': avg([(r.team_kills or 0) + (r.team_deaths or 0) for r in rows if r.team_kills is not None or r.team_deaths is not None]),
        'avg_towers': avg([r.towers for r in rows]),
        'avg_inhibitors': avg([r.inhibitors for r in rows]),
        'avg_dragons': avg([r.dragons for r in rows]),
        'avg_barons': avg([r.barons for r in rows]),
        'avg_game_duration_seconds': avg([r.game_length_seconds for r in rows]),
        'first_blood_rate': rate([r.first_blood for r in rows]),
        'first_tower_rate': rate([r.first_tower for r in rows]),
    }


def matchup_metrics(session: Session, team_a: str, team_b: str, league: str | None = None, window: int = 20) -> dict:
    a = team_metrics(session, team_a, league, window)
    b = team_metrics(session, team_b, league, window)
    sample = min(a['sample_size'], b['sample_size'])
    conf = min(a['confidence'], b['confidence'])
    return {
        'team_a': a,
        'team_b': b,
        'league': league,
        'sample_size': sample,
        'confidence': conf,
        'avg_total_kills': avg([a.get('avg_total_kills'), b.get('avg_total_kills')]),
        'avg_combined_kills': (a.get('avg_kills') or 0) + (b.get('avg_kills') or 0) if a.get('avg_kills') is not None and b.get('avg_kills') is not None else None,
        'avg_towers_total': (a.get('avg_towers') or 0) + (b.get('avg_towers') or 0) if a.get('avg_towers') is not None and b.get('avg_towers') is not None else None,
        'avg_inhibitors_total': (a.get('avg_inhibitors') or 0) + (b.get('avg_inhibitors') or 0) if a.get('avg_inhibitors') is not None and b.get('avg_inhibitors') is not None else None,
        'avg_dragons_total': (a.get('avg_dragons') or 0) + (b.get('avg_dragons') or 0) if a.get('avg_dragons') is not None and b.get('avg_dragons') is not None else None,
        'avg_barons_total': (a.get('avg_barons') or 0) + (b.get('avg_barons') or 0) if a.get('avg_barons') is not None and b.get('avg_barons') is not None else None,
        'avg_game_duration_seconds': avg([a.get('avg_game_duration_seconds'), b.get('avg_game_duration_seconds')]),
    }


def player_rows(session: Session, player: str, role: str | None = None, league: str | None = None, window: int | None = None):
    query = select(LolPlayerGameStat).where(LolPlayerGameStat.player_name == player)
    if role:
        query = query.where(LolPlayerGameStat.role == role)
    if league:
        query = query.where(LolPlayerGameStat.league == league)
    rows = ordered_recent(session.exec(query).all())
    return rows[:window] if window else rows


def player_metrics(session: Session, player: str, role: str | None = None, league: str | None = None, window: int = 20) -> dict:
    rows = player_rows(session, player, role, league, window)
    sample = len(rows)
    min_games = getattr(settings, 'lol_history_min_games_player', 5)
    deaths = [r.deaths for r in rows if r.deaths is not None]
    kda_values = []
    for r in rows:
        if r.kills is not None and r.deaths is not None and r.assists is not None:
            kda_values.append((r.kills + r.assists) / max(1, r.deaths))
    return {
        'player': player,
        'role': role,
        'league': league,
        'window': window,
        'sample_size': sample,
        'confidence': confidence(sample, min_games),
        'avg_kills': avg([r.kills for r in rows]),
        'avg_deaths': avg(deaths),
        'avg_assists': avg([r.assists for r in rows]),
        'avg_kda': avg(kda_values),
        'avg_cs': avg([r.cs for r in rows]),
        'avg_damage': avg([r.damage for r in rows]),
        'avg_gold': avg([r.gold for r in rows]),
    }


def probability_over_under(mean_value: float | None, line: float | None, selection: str | None) -> float | None:
    if mean_value is None or line is None:
        return None
    # Smooth deterministic approximation: each 10% distance from line moves probability by 5pp.
    spread = max(1.0, abs(line) * 0.10)
    prob_over = 0.5 + max(-0.35, min(0.35, (mean_value - line) / spread * 0.05))
    if (selection or '').lower() in ('under', 'menos'):
        return 1.0 - prob_over
    return prob_over
