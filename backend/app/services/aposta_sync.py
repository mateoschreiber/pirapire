from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

from sqlmodel import Session, select

from ..config import settings
from ..models_aposta import ApostaEvent, ApostaMarket, ApostaSelection, ApostaSyncRun
from ..models_imports import ImportedOdds, ManualImportBatch
from . import aposta_snapshot_parser
from .event_matcher import match_imported_odd
from .market_mapper import map_market


def now():
    return datetime.now(UTC)


def normalized_datetime(value):
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def is_current_odd(odd: ImportedOdds) -> bool:
    if odd.event_date is None:
        return True
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=settings.recommender_event_grace_minutes)
    return normalized_datetime(odd.event_date) >= cutoff


def filter_current_odds(odds: list[ImportedOdds]) -> list[ImportedOdds]:
    return [odd for odd in odds if is_current_odd(odd)]


def ensure_dirs() -> None:
    for folder in (settings.aposta_import_dir, settings.aposta_archive_dir, settings.aposta_error_dir):
        Path(folder).mkdir(parents=True, exist_ok=True)


def read_url(url: str) -> str:
    req = Request(url, headers={'User-Agent': 'Pirapire/1.0'})
    with urlopen(req, timeout=20) as res:
        return res.read().decode('utf-8')


def load_snapshot() -> tuple[str, list[tuple[str, str]]]:
    mode = (settings.aposta_sync_mode or 'disabled').strip().lower()
    ensure_dirs()
    if mode == 'disabled' or not settings.aposta_sync_enabled:
        return 'manual_required', []
    if mode == 'csv_folder':
        folder = Path(settings.aposta_import_dir)
        files = sorted(folder.glob('*.csv'))
        return mode, [(f.name, f.read_text(encoding='utf-8-sig')) for f in files]
    if mode == 'json_url' and settings.aposta_json_url.strip():
        return mode, [('aposta-json-url', read_url(settings.aposta_json_url.strip()))]
    if mode == 'browser_worker' and settings.aposta_browser_worker_url.strip():
        base = settings.aposta_browser_worker_url.strip().rstrip('/')
        return mode, [('aposta-browser-worker', read_url(base + '/snapshot'))]
    return 'manual_required', []


def parse_source(name: str, text: str) -> tuple[list[dict], list[str]]:
    if name.lower().endswith('.csv'):
        return aposta_snapshot_parser.parse_csv(text)
    stripped = text.lstrip()
    if stripped.startswith('{') or stripped.startswith('['):
        return aposta_snapshot_parser.parse_json(text)
    return aposta_snapshot_parser.parse_csv(text)


def normalized_key(row: dict, batch_id: int) -> str:
    payload = [
        batch_id,
        row.get('sport'), row.get('competition'), str(row.get('event_date')), row.get('team_a'), row.get('team_b'),
        row.get('market_text'), str(row.get('line')), row.get('selection'), str(row.get('odds_decimal')), 'Aposta.LA',
    ]
    return 'aposta:' + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]


def store_row(session: Session, batch: ManualImportBatch, row: dict) -> tuple[ImportedOdds, bool]:
    market_id, market_code = map_market(session, row['sport'], row['market_text'])
    odd = ImportedOdds(
        batch_id=batch.id,
        sport=row['sport'],
        bookmaker='Aposta.LA',
        competition=row.get('competition'),
        event_date=row.get('event_date'),
        team_a=row.get('team_a'),
        team_b=row.get('team_b'),
        market_text=row['market_text'],
        market_id=market_id,
        market_code=market_code,
        line=row.get('line'),
        selection=row.get('selection'),
        odds_decimal=row['odds_decimal'],
        normalized_key=normalized_key(row, batch.id),
        source_name='aposta_la',
    )
    session.add(odd)
    session.commit()
    session.refresh(odd)
    return odd, market_id is not None


def mirror_aposta_tables(session: Session, odds: list[ImportedOdds], run: ApostaSyncRun) -> None:
    for sel in session.exec(select(ApostaSelection)).all():
        sel.is_active = False
        session.add(sel)
    session.commit()
    event_cache = {}
    market_cache = {}
    for odd in odds:
        event_key = '|'.join([odd.sport or '', odd.competition or '', odd.team_a or '', odd.team_b or '', str(odd.event_date or '')])
        event = event_cache.get(event_key)
        if event is None:
            event = ApostaEvent(
                sport=odd.sport,
                competition=odd.competition,
                team_a=odd.team_a,
                team_b=odd.team_b,
                event_name=' vs '.join([p for p in [odd.team_a, odd.team_b] if p]),
                start_time=odd.event_date,
                external_id=f'run-{run.id}-{len(event_cache)+1}',
                status='active',
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            event_cache[event_key] = event
        market_key = event_key + '|' + (odd.market_text or '') + '|' + str(odd.line or '')
        market = market_cache.get(market_key)
        if market is None:
            market = ApostaMarket(
                event_id=event.id,
                market_text=odd.market_text,
                market_id=odd.market_id,
                market_code=odd.market_code,
                line=odd.line,
                is_mapped=odd.market_id is not None,
                source_status='current',
            )
            session.add(market)
            session.commit()
            session.refresh(market)
            market_cache[market_key] = market
        session.add(ApostaSelection(
            market_id=market.id,
            selection_text=odd.selection or '',
            selection_normalized=odd.selection,
            odds_decimal=odd.odds_decimal,
            implied_probability=1.0 / odd.odds_decimal if odd.odds_decimal else None,
            is_active=True,
        ))
    session.commit()


def latest_aposta_batch(session: Session) -> ManualImportBatch | None:
    return session.exec(
        select(ManualImportBatch)
        .where(ManualImportBatch.import_type == 'aposta_odds', ManualImportBatch.status.in_(['success', 'partial']))
        .order_by(ManualImportBatch.id.desc())
    ).first()


def current_odds(session: Session, include_stale: bool = False, include_past: bool = False) -> list[ImportedOdds]:
    query = select(ImportedOdds).where(ImportedOdds.source_name == 'aposta_la')
    if not include_stale:
        batch = latest_aposta_batch(session)
        if batch is None:
            return []
        query = query.where(ImportedOdds.batch_id == batch.id)
    rows = session.exec(query.order_by(ImportedOdds.id.desc())).all()
    if include_past:
        return rows
    return filter_current_odds(rows)


def sync(session: Session, force_refresh: bool = False) -> dict:
    run = ApostaSyncRun(status='running', requested_by='dashboard')
    session.add(run)
    session.commit()
    session.refresh(run)
    warnings = []
    imported = []
    try:
        mode, sources = load_snapshot()
        if mode == 'manual_required' or not sources:
            run.status = 'manual_required'
            run.finished_at = now()
            run.message = 'Colocar CSV en /opt/pirapire/data/imports/aposta o configurar APOSTA_BROWSER_WORKER_URL.'
            session.add(run)
            session.commit()
            session.refresh(run)
            return {'run': run, 'imported': 0, 'mapped': 0, 'unmapped': 0, 'warnings': [run.message]}

        batch = ManualImportBatch(sport='mixed', import_type='aposta_odds', filename=f'aposta_run_{run.id}')
        session.add(batch)
        session.commit()
        session.refresh(batch)

        mapped = 0
        unmapped = 0
        parsed_rows = 0
        for name, text in sources:
            rows, errors = parse_source(name, text)
            warnings.extend(errors[:20])
            parsed_rows += len(rows)
            for row in rows:
                odd, ok = store_row(session, batch, row)
                imported.append(odd)
                if ok:
                    mapped += 1
                else:
                    unmapped += 1
        batch.imported_rows = len(imported)
        batch.total_rows = parsed_rows + len(warnings)
        batch.error_rows = len(warnings)
        batch.status = 'success' if imported and not warnings else ('partial' if imported else 'error')
        batch.message = f'{len(imported)} Aposta.LA odds imported from {mode}'
        batch.finished_at = now()
        session.add(batch)

        current_imported = filter_current_odds(imported)
        past_imported = len(imported) - len(current_imported)
        mirror_aposta_tables(session, current_imported, run)
        run.status = batch.status
        run.finished_at = now()
        run.captured_responses = len(sources)
        run.parsed_events = len({(o.sport, o.team_a, o.team_b, o.event_date) for o in imported})
        run.parsed_markets = len({(o.market_text, o.line) for o in imported})
        run.parsed_selections = len(imported)
        run.mapped_markets = mapped
        run.unmapped_markets = unmapped
        run.error_count = len(warnings)
        run.message = batch.message
        if past_imported:
            run.message += f'; {past_imported} cuotas vencidas quedan solo como historial/estadistica'
        session.add(run)
        session.commit()
        session.refresh(run)
        return {'run': run, 'imported': len(imported), 'mapped': mapped, 'unmapped': unmapped, 'warnings': warnings}
    except Exception as exc:
        run.status = 'error'
        run.finished_at = now()
        run.error_count = 1
        run.message = str(exc)
        session.add(run)
        session.commit()
        session.refresh(run)
        return {'run': run, 'imported': 0, 'mapped': 0, 'unmapped': 0, 'warnings': [str(exc)]}


def match_summary(session: Session, odds: list[ImportedOdds]) -> tuple[int, int]:
    matched = 0
    for odd in odds:
        if match_imported_odd(session, odd).get('match_confidence', 0.0) >= settings.recommender_min_match_confidence:
            matched += 1
    return matched, max(0, len(odds) - matched)
