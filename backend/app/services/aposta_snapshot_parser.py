import csv
import io
import json
from datetime import datetime
from typing import Any

from .imports import csv_utils
from .market_mapper import normalize_text

HEADER_ALIASES = {
    'sport': ('sport', 'deporte'),
    'competition': ('competition', 'competicion', 'competición', 'competencia', 'liga', 'torneo'),
    'event_date': ('event_date', 'fecha', 'fecha_evento', 'inicio', 'start_time', 'hora'),
    'team_a': ('team_a', 'local', 'equipo_local', 'team_home', 'home', 'equipo_a'),
    'team_b': ('team_b', 'visitante', 'equipo_visitante', 'team_away', 'away', 'equipo_b'),
    'market_text': ('market_text', 'mercado', 'market', 'tipo_mercado'),
    'line': ('line', 'linea', 'línea', 'handicap', 'total'),
    'selection': ('selection', 'seleccion', 'selección', 'pick', 'opcion', 'opción'),
    'odds_decimal': ('odds_decimal', 'cuota', 'odds', 'decimal', 'precio'),
    'bookmaker': ('bookmaker', 'casa', 'casa_apuestas'),
}


def header_key(value: str | None) -> str:
    return normalize_text(value or '').replace(' ', '_')


def get_value(row: dict[str, Any], canonical: str) -> Any:
    keyed = {header_key(k): v for k, v in row.items()}
    for alias in HEADER_ALIASES[canonical]:
        val = keyed.get(header_key(alias))
        if val not in (None, ''):
            return val
    return None


def safe_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().replace(',', '.')
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def safe_date(value: Any):
    if value is None or value == '':
        return None
    if isinstance(value, datetime):
        return value
    return csv_utils.parse_event_date(str(value))


def normalize_row(row: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    sport = csv_utils.normalise_sport(str(get_value(row, 'sport') or ''))
    team_a = str(get_value(row, 'team_a') or '').strip()
    team_b = str(get_value(row, 'team_b') or '').strip()
    market_text = str(get_value(row, 'market_text') or '').strip()
    odds = safe_float(get_value(row, 'odds_decimal'))
    if not sport:
        return None, 'missing sport/deporte'
    if not team_a or not team_b:
        return None, 'missing team_a/team_b'
    if not market_text:
        return None, 'missing market_text/mercado'
    if odds is None or odds <= 1:
        return None, 'invalid odds_decimal/cuota'
    bookmaker = str(get_value(row, 'bookmaker') or 'Aposta.LA').strip() or 'Aposta.LA'
    selection_raw = str(get_value(row, 'selection') or '').strip()
    return {
        'sport': sport,
        'competition': str(get_value(row, 'competition') or '').strip() or None,
        'event_date': safe_date(get_value(row, 'event_date')),
        'team_a': team_a,
        'team_b': team_b,
        'market_text': market_text,
        'line': safe_float(get_value(row, 'line')),
        'selection': csv_utils.normalise_selection(selection_raw) or selection_raw or None,
        'odds_decimal': odds,
        'bookmaker': 'Aposta.LA' if 'aposta' in normalize_text(bookmaker) else bookmaker,
    }, None


def parse_csv(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        raise ValueError('CSV file has no headers')
    rows = []
    errors = []
    for row_no, raw in enumerate(reader, start=2):
        normalized, err = normalize_row(raw)
        if normalized:
            rows.append(normalized)
        else:
            errors.append(f'row {row_no}: {err}')
    return rows, errors


def json_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        for key in ('odds', 'options', 'selections', 'rows', 'events'):
            value = payload.get(key)
            if isinstance(value, list):
                if key != 'events':
                    return [r for r in value if isinstance(r, dict)]
                flattened = []
                for event in value:
                    if not isinstance(event, dict):
                        continue
                    for market in event.get('markets') or []:
                        for sel in market.get('selections') or market.get('options') or []:
                            merged = dict(event)
                            if isinstance(market, dict):
                                merged.update(market)
                            if isinstance(sel, dict):
                                merged.update(sel)
                            flattened.append(merged)
                return flattened
    return []


def parse_json(text: str) -> tuple[list[dict[str, Any]], list[str]]:
    payload = json.loads(text)
    rows = []
    errors = []
    for row_no, raw in enumerate(json_rows(payload), start=1):
        normalized, err = normalize_row(raw)
        if normalized:
            rows.append(normalized)
        else:
            errors.append(f'json row {row_no}: {err}')
    return rows, errors
