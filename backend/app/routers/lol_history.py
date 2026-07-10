from fastapi import APIRouter, Depends
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..models_lol import LolDataCoverage, LolGameHistory, LolLeague, LolPlayerGameStat, LolTeamGameStat
from ..services import lol_historical_importer, lol_metrics_engine
from ..services.lol_league_catalog import seed_catalog

router = APIRouter(prefix='/lol-history', tags=['lol-history'])


@router.get('/status')
def status(session: Session = Depends(get_session)) -> dict:
    seed_catalog(session)
    games = session.exec(select(func.count()).select_from(LolGameHistory)).one()
    teams = session.exec(select(func.count(func.distinct(LolTeamGameStat.team_name)))).one()
    players = session.exec(select(func.count(func.distinct(LolPlayerGameStat.player_name)))).one()
    leagues = session.exec(select(func.count(func.distinct(LolGameHistory.league)))).one()
    last_cov = session.exec(select(LolDataCoverage).order_by(LolDataCoverage.last_imported_at.desc())).first()
    return {
        'enabled': settings.lol_history_enabled,
        'import_dir': settings.lol_history_import_dir,
        'host_import_dir': '/opt/pirapire/data/imports/oracles',
        'active_leagues': [x.strip() for x in settings.lol_history_active_leagues.split(',') if x.strip()],
        'include_legacy': settings.lol_history_include_legacy,
        'games_count': games,
        'teams_count': teams,
        'players_count': players,
        'leagues_count': leagues,
        'last_imported_at': last_cov.last_imported_at if last_cov else None,
        'message': None if games else 'Copiar CSV reales de Oracle\'s Elixir a /opt/pirapire/data/imports/oracles y ejecutar /lol-history/import',
    }


@router.post('/import')
def import_all(session: Session = Depends(get_session)) -> dict:
    return lol_historical_importer.import_folder(session)


@router.post('/import-year/{year}')
def import_year(year: int, session: Session = Depends(get_session)) -> dict:
    return lol_historical_importer.import_year(session, year)


@router.get('/leagues')
def leagues(session: Session = Depends(get_session)) -> list:
    seed_catalog(session)
    return session.exec(select(LolLeague).order_by(LolLeague.active.desc(), LolLeague.slug)).all()


@router.get('/coverage')
def coverage(session: Session = Depends(get_session)) -> list:
    return session.exec(select(LolDataCoverage).order_by(LolDataCoverage.league, LolDataCoverage.year.desc())).all()


@router.get('/team-metrics')
def team_metrics(team: str, league: str | None = None, window: int = 20, session: Session = Depends(get_session)) -> dict:
    return lol_metrics_engine.team_metrics(session, team=team, league=league, window=window)


@router.get('/player-metrics')
def player_metrics(player: str, role: str | None = None, league: str | None = None, window: int = 20, session: Session = Depends(get_session)) -> dict:
    return lol_metrics_engine.player_metrics(session, player=player, role=role, league=league, window=window)
