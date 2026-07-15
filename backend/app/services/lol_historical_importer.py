import csv
import io
import shutil
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import Request, urlopen

from sqlmodel import Session, select

from ..config import settings
from ..models_imports import ManualImportBatch
from ..models_lol import LolDataCoverage, LolGameHistory, LolPlayerGameStat, LolTeamGameStat
from .imports import csv_utils
from .lol_league_catalog import ACTIVE_LEAGUES, LEGACY_LEAGUES, canonical_league, seed_catalog
from .lol_team_aliases import canonical_team, upsert_alias

REQUIRED_COLUMNS = {'gameid', 'league', 'date', 'position', 'teamname'}
SOURCE_NAME = 'oracles_elixir'


def now() -> datetime:
    return datetime.now(UTC)


def import_dir() -> Path:
    return Path(getattr(settings, 'lol_history_import_dir', '/app/data/imports/oracles'))


def archive_dir() -> Path:
    return Path(getattr(settings, 'aposta_archive_dir', '/app/data/imports/archive'))


def error_dir() -> Path:
    return Path(getattr(settings, 'aposta_error_dir', '/app/data/imports/errors'))


def ensure_dirs() -> None:
    for path in (import_dir(), archive_dir(), error_dir()):
        path.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    raw = path.read_bytes()
    for enc in ('utf-8-sig', 'utf-8', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('latin-1', errors='replace')


def rows_from_text(text: str) -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError('CSV sin encabezados')
    headers = {h.strip().lower() for h in reader.fieldnames if h}
    missing = sorted(REQUIRED_COLUMNS - headers)
    if missing:
        raise ValueError('faltan columnas Oracle: ' + ', '.join(missing))
    return list(reader)


def col(row: dict, name: str):
    return csv_utils.col(row, name)


def parse_year(row: dict, fallback: int | None = None) -> int | None:
    y = csv_utils.safe_int(col(row, 'year'))
    if y:
        return y
    date = col(row, 'date') or ''
    if len(date) >= 4 and date[:4].isdigit():
        return int(date[:4])
    return fallback


def total_cs(row: dict) -> int | None:
    direct = csv_utils.safe_int(col(row, 'total cs'))
    if direct is not None:
        return direct
    return (csv_utils.safe_int(col(row, 'minionkills')) or 0) + (csv_utils.safe_int(col(row, 'monsterkills')) or 0) or None


def league_allowed(league: str | None) -> bool:
    if not league:
        return False
    active = {x.strip().upper() for x in getattr(settings, 'lol_history_active_leagues', 'LCK,LPL,LEC,LCS,CBLOL,LCP,MSI,WORLDS,FIRST_STAND').split(',') if x.strip()}
    legacy = {x.strip().upper() for x in getattr(settings, 'lol_history_legacy_leagues', 'LTA,LLA,PCS,VCS,LJL,LCO,TCL,LCL').split(',') if x.strip()}
    if league in active:
        return True
    return bool(getattr(settings, 'lol_history_include_legacy', True) and league in legacy)


def source_key(*parts) -> str:
    return '|'.join(str(p or '').strip() for p in parts)


def get_or_create_game(session: Session, row: dict, year: int | None, league: str | None) -> LolGameHistory:
    gameid = (col(row, 'gameid') or '').strip()
    key = source_key(SOURCE_NAME, year, gameid)
    game = session.exec(select(LolGameHistory).where(LolGameHistory.source_key == key)).first()
    if game:
        return game
    game = LolGameHistory(
        source_name=SOURCE_NAME,
        source_game_id=gameid,
        year=year,
        league=league,
        split=col(row, 'split'),
        playoffs=csv_utils.safe_bool(col(row, 'playoffs')),
        date=col(row, 'date'),
        patch=col(row, 'patch'),
        game_number=csv_utils.safe_int(col(row, 'game')),
        game_length_seconds=csv_utils.parse_game_length_seconds(col(row, 'gamelength')),
        source_key=key,
    )
    session.add(game)
    session.commit()
    session.refresh(game)
    return game


def upsert_team_stat(session: Session, game: LolGameHistory, row: dict, year: int | None, league: str | None) -> bool:
    raw_team = (col(row, 'teamname') or '').strip()
    team = canonical_team(session, raw_team, league) or raw_team
    opponent = (col(row, 'opponent') or '').strip() or None
    if team:
        upsert_alias(session, team, raw_team, league)
    key = source_key(SOURCE_NAME, year, game.source_game_id, 'team', team, col(row, 'side'))
    if session.exec(select(LolTeamGameStat).where(LolTeamGameStat.source_key == key)).first():
        return False
    result = csv_utils.safe_int(col(row, 'result'))
    stat = LolTeamGameStat(
        game_id=game.id,
        source_name=SOURCE_NAME,
        source_game_id=game.source_game_id,
        year=year,
        league=league,
        date=col(row, 'date'),
        patch=col(row, 'patch'),
        team_name=team or '?',
        opponent_name=opponent,
        side=col(row, 'side'),
        result=result,
        kills=csv_utils.safe_int(col(row, 'kills')),
        deaths=csv_utils.safe_int(col(row, 'deaths')),
        assists=csv_utils.safe_int(col(row, 'assists')),
        team_kills=csv_utils.safe_int(col(row, 'teamkills')),
        team_deaths=csv_utils.safe_int(col(row, 'teamdeaths')),
        dragons=csv_utils.safe_int(col(row, 'dragons')),
        barons=csv_utils.safe_int(col(row, 'barons')),
        towers=csv_utils.safe_int(col(row, 'towers')),
        inhibitors=csv_utils.safe_int(col(row, 'inhibitors')),
        game_length_seconds=csv_utils.parse_game_length_seconds(col(row, 'gamelength')),
        first_blood=csv_utils.safe_bool(col(row, 'firstblood')),
        first_tower=csv_utils.safe_bool(col(row, 'firsttower')),
        gold=csv_utils.safe_int(col(row, 'earnedgold')),
        source_key=key,
    )
    session.add(stat)
    if (col(row, 'side') or '').lower() == 'blue':
        game.blue_team = team
    if (col(row, 'side') or '').lower() == 'red':
        game.red_team = team
    if result == 1:
        game.winner_team = team
    session.add(game)
    return True


def upsert_player_stat(session: Session, game: LolGameHistory, row: dict, year: int | None, league: str | None) -> bool:
    player = (col(row, 'playername') or '').strip() or None
    role = (col(row, 'position') or '').strip() or None
    team = canonical_team(session, col(row, 'teamname'), league) or col(row, 'teamname')
    key = source_key(SOURCE_NAME, year, game.source_game_id, 'player', player, role)
    if session.exec(select(LolPlayerGameStat).where(LolPlayerGameStat.source_key == key)).first():
        return False
    session.add(LolPlayerGameStat(
        game_id=game.id,
        source_name=SOURCE_NAME,
        source_game_id=game.source_game_id,
        year=year,
        league=league,
        date=col(row, 'date'),
        patch=col(row, 'patch'),
        team_name=team,
        player_name=player,
        role=role,
        champion=col(row, 'champion'),
        kills=csv_utils.safe_int(col(row, 'kills')),
        deaths=csv_utils.safe_int(col(row, 'deaths')),
        assists=csv_utils.safe_int(col(row, 'assists')),
        cs=total_cs(row),
        damage=csv_utils.safe_int(col(row, 'damagetochampions')),
        gold=csv_utils.safe_int(col(row, 'earnedgold')),
        source_key=key,
    ))
    return True


def refresh_coverage(session: Session) -> None:
    pairs = session.exec(select(LolTeamGameStat.league, LolTeamGameStat.year).distinct()).all()
    for league, year in pairs:
        if not league or not year:
            continue
        teams = session.exec(select(LolTeamGameStat).where(LolTeamGameStat.league == league, LolTeamGameStat.year == year)).all()
        players = session.exec(select(LolPlayerGameStat).where(LolPlayerGameStat.league == league, LolPlayerGameStat.year == year)).all()
        games = {t.source_game_id for t in teams}
        team_names = {t.team_name for t in teams if t.team_name}
        player_names = {p.player_name for p in players if p.player_name}
        cov = session.exec(select(LolDataCoverage).where(LolDataCoverage.league == league, LolDataCoverage.year == year)).first()
        if cov is None:
            cov = LolDataCoverage(league=league, year=year)
        cov.games_count = len(games)
        cov.teams_count = len(team_names)
        cov.players_count = len(player_names)
        cov.last_imported_at = now()
        session.add(cov)
    session.commit()


def import_text(session: Session, text: str, filename: str = 'oracle.csv', fallback_year: int | None = None) -> dict:
    seed_catalog(session)
    rows = rows_from_text(text)
    batch = ManualImportBatch(sport='lol', import_type='lol_history_oracles', filename=filename, original_filename=filename)
    session.add(batch)
    session.commit()
    session.refresh(batch)
    imported = skipped = filtered = errors = 0
    for idx, row in enumerate(rows, start=2):
        try:
            league = canonical_league(col(row, 'league'))
            if not league_allowed(league):
                filtered += 1
                continue
            year = parse_year(row, fallback_year)
            game = get_or_create_game(session, row, year, league)
            position = (col(row, 'position') or '').strip().lower()
            if position == 'team':
                changed = upsert_team_stat(session, game, row, year, league)
            else:
                changed = upsert_player_stat(session, game, row, year, league)
            if changed:
                imported += 1
            else:
                skipped += 1
            if imported % 500 == 0:
                session.commit()
        except Exception as exc:
            errors += 1
            if errors <= 10:
                csv_utils.log_import_error(session, batch, idx, 'row parse error: ' + str(exc), row, 'error')
    session.commit()
    refresh_coverage(session)
    batch.imported_rows = imported
    batch.skipped_rows = skipped + filtered
    batch.error_rows = errors
    batch.total_rows = imported + skipped + filtered + errors
    batch.status = 'success' if errors == 0 else ('partial' if imported else 'error')
    batch.message = 'imported=%s skipped=%s filtered=%s errors=%s' % (imported, skipped, filtered, errors)
    csv_utils.finish_batch(session, batch, batch.status, batch.message)
    return {'batch_id': batch.id, 'status': batch.status, 'imported': imported, 'skipped': skipped, 'filtered': filtered, 'errors': errors}


def import_folder(session: Session) -> dict:
    ensure_dirs()
    files = sorted(import_dir().glob('*.csv'))
    if not files:
        return {'status': 'manual_required', 'files': 0, 'message': 'Copiar CSV reales de Oracle\'s Elixir a /opt/pirapire/data/imports/oracles'}
    results = []
    for path in files:
        try:
            result = import_text(session, read_text(path), filename=path.name)
            results.append(result)
            target = archive_dir() / path.name
            shutil.move(str(path), str(target))
        except Exception as exc:
            results.append({'status': 'error', 'file': path.name, 'message': str(exc)})
            shutil.move(str(path), str(error_dir() / path.name))
    imported = sum(r.get('imported', 0) for r in results)
    errors = sum(r.get('errors', 0) for r in results if isinstance(r, dict))
    status = 'success' if imported and errors == 0 else ('partial' if imported else 'error')
    return {'status': status, 'files': len(files), 'imported': imported, 'errors': errors, 'results': results}


def import_year(session: Session, year: int) -> dict:
    ensure_dirs()
    local = sorted(import_dir().glob('*%s*.csv' % year))
    if local:
        total = {'status': 'success', 'files': 0, 'imported': 0, 'errors': 0, 'results': []}
        for path in local:
            res = import_text(session, read_text(path), filename=path.name, fallback_year=year)
            total['files'] += 1
            total['imported'] += res.get('imported', 0)
            total['errors'] += res.get('errors', 0)
            total['results'].append(res)
        return total
    if getattr(settings, 'lol_history_allow_download', False):
        url = getattr(settings, 'lol_history_download_url_template', '').format(year=year)
        req = Request(url, headers={'User-Agent': 'Pirapire/1.0'})
        with urlopen(req, timeout=30) as res:
            text = res.read().decode('utf-8-sig')
        return import_text(session, text, filename='oracles_%s.csv' % year, fallback_year=year)
    return {'status': 'manual_required', 'message': 'No hay CSV local para %s en /opt/pirapire/data/imports/oracles' % year}
