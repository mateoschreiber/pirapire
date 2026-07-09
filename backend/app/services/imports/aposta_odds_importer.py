"""Import odds CSV (Aposta.LA format)."""

import hashlib
import json

from sqlmodel import Session

from . import csv_utils
from ...models_imports import ImportedOdds, ManualImportBatch
from ..market_mapper import map_market

ODDS_COLUMNS = {
    "sport": "sport",
    "competition": "competition",
    "event_date": "event_date",
    "team_a": "team_a",
    "team_b": "team_b",
    "market_text": "market_text",
    "line": "line",
    "selection": "selection",
    "odds_decimal": "odds_decimal",
    "bookmaker": "bookmaker",
}


def import_csv(session: Session, batch: ManualImportBatch, csv_text: str) -> ManualImportBatch:
    try:
        rows = csv_utils.read_rows(csv_text)
    except Exception as exc:
        return csv_utils.finish_batch(session, batch, "error", f"failed to parse CSV: {exc}")

    imported = 0
    unmapped_warning = False
    unmapped_texts: set[str] = set()

    for i, row in enumerate(rows, start=2):
        try:
            sport = csv_utils.normalise_sport(row.get(ODDS_COLUMNS["sport"]))
            if not sport:
                csv_utils.log_import_error(session, batch, i, "invalid or missing sport", row, "error")
                continue

            competition = (row.get(ODDS_COLUMNS["competition"]) or "").strip() or None
            event_date = csv_utils.parse_event_date(row.get(ODDS_COLUMNS["event_date"]))
            team_a = (row.get(ODDS_COLUMNS["team_a"]) or "").strip() or None
            team_b = (row.get(ODDS_COLUMNS["team_b"]) or "").strip() or None
            market_text = (row.get(ODDS_COLUMNS["market_text"]) or "").strip()
            line = csv_utils.safe_float(row.get(ODDS_COLUMNS["line"]))
            selection = csv_utils.normalise_selection(row.get(ODDS_COLUMNS["selection"]))
            odds = csv_utils.safe_float(row.get(ODDS_COLUMNS["odds_decimal"]))
            bookmaker = (row.get(ODDS_COLUMNS["bookmaker"]) or "").strip() or "ApostaLA"

            if not team_a or not team_b:
                csv_utils.log_import_error(session, batch, i, "team_a/team_b are required", row, "error")
                continue

            if not market_text or odds is None or odds <= 1:
                csv_utils.log_import_error(session, batch, i, "invalid market_text or odds_decimal", row, "error")
                continue

            market_id, market_code = map_market(session, sport, market_text)
            if market_id is None:
                unmapped_texts.add(market_text)

            normalized_key = "imp:" + hashlib.sha256(
                json.dumps([sport, team_a, team_b, market_text, str(line), selection, str(odds), bookmaker],
                           sort_keys=True).encode()
            ).hexdigest()[:32]

            session.add(
                ImportedOdds(
                    batch_id=batch.id,
                    sport=sport,
                    bookmaker=bookmaker,
                    competition=competition,
                    event_date=event_date,
                    team_a=team_a,
                    team_b=team_b,
                    market_text=market_text,
                    market_id=market_id,
                    market_code=market_code,
                    line=line,
                    selection=selection,
                    odds_decimal=odds,
                    normalized_key=normalized_key,
                )
            )
            imported += 1
        except Exception as exc:
            csv_utils.log_import_error(session, batch, i, f"row parse error: {exc}", row, "error")

    batch.imported_rows = imported
    msg_parts = [f"{imported} rows imported"]
    if unmapped_texts:
        unmapped_warning = True
        msg_parts.append(f"unmapped markets: {sorted(unmapped_texts)}")

    status = "success" if batch.error_rows == 0 and not unmapped_warning else "partial"
    return csv_utils.finish_batch(session, batch, status, "; ".join(msg_parts))
