from __future__ import annotations

import hashlib
import json
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

from sqlmodel import Session, select

from ..config import settings
from ..models_aposta import ApostaEvent, ApostaMarket, ApostaSelection, ApostaSyncRun
from ..models_imports import ImportedOdds, ManualImportBatch
from . import aposta_html_parser
from . import aposta_lol_parser
from . import aposta_snapshot_parser
from .aposta_snapshot import current_odds as snapshot_current_odds
from .aposta_snapshot import expired_odds as snapshot_expired_odds
from .aposta_snapshot import mark_expired, set_current_batch
from .event_matcher import match_and_store
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
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(
        minutes=settings.recommender_event_grace_minutes
    )
    return normalized_datetime(odd.event_date) >= cutoff


def filter_current_odds(odds: list[ImportedOdds]) -> list[ImportedOdds]:
    return [odd for odd in odds if is_current_odd(odd)]


def ensure_dirs() -> None:
    for folder in (
        settings.aposta_import_dir,
        settings.aposta_archive_dir,
        settings.aposta_error_dir,
    ):
        Path(folder).mkdir(parents=True, exist_ok=True)


def _import_paths() -> tuple[Path, Path, Path]:
    return (
        Path(settings.aposta_import_dir),
        Path(settings.aposta_archive_dir),
        Path(settings.aposta_error_dir),
    )


def read_url(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Pirapire/1.0"})
    with urlopen(req, timeout=20) as res:
        return res.read().decode("utf-8")


def load_snapshot() -> tuple[str, list[tuple[str, str, Path | None]]]:
    mode = (settings.aposta_sync_mode or "disabled").strip().lower()
    ensure_dirs()
    import_dir, _, _ = _import_paths()
    if mode == "disabled" or not settings.aposta_sync_enabled:
        return "manual_required", []
    if mode == "csv_folder":
        files = sorted(import_dir.glob("*.csv"))
        return mode, [(f.name, f.read_text(encoding="utf-8-sig"), f) for f in files]
    if mode == "json_url" and settings.aposta_json_url.strip():
        return mode, [
            ("aposta-json-url", read_url(settings.aposta_json_url.strip()), None)
        ]
    if mode == "browser_worker" and settings.aposta_browser_worker_url.strip():
        base = settings.aposta_browser_worker_url.strip().rstrip("/")
        return mode, [("aposta-browser-worker", read_url(base + "/snapshot"), None)]
    if mode == "aposta_fetch" and settings.aposta_fetch_urls.strip():
        urls = [u.strip() for u in settings.aposta_fetch_urls.split(",") if u.strip()]
        sources = []
        for url in urls:
            try:
                html = read_url(url)
                sources.append((f"aposta-fetch:{url}", html, None))
            except Exception as e:
                import logging

                logging.getLogger(__name__).warning(f"Failed to fetch {url}: {e}")
        # Kambi API for LoL events
        try:
            from . import kambi_lol_connector

            lol_data = kambi_lol_connector.fetch_lol_events()
            lol_rows = kambi_lol_connector.parse_kambi_to_rows(
                lol_data, fetch_details=True
            )
            if lol_rows:
                import json

                sources.append(("aposta-lol-kambi", json.dumps(lol_rows), None))
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"LoL Kambi fetch failed: {e}")
        return mode, sources
    return "manual_required", []


def parse_source(name: str, text: str) -> tuple[list[dict], list[str]]:
    if name.lower().endswith(".csv"):
        return aposta_snapshot_parser.parse_csv(text)
    if name.startswith("aposta-fetch:"):
        rows = aposta_html_parser.parse_aposta_html(text, name)
        return rows, []
    if name.startswith("aposta-lol-kambi"):
        import json

        rows = json.loads(text)
        return rows, []
    if name.startswith("aposta-lol-browser"):
        rows = aposta_lol_parser.parse_lol_html(text, name)
        return rows, []
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        return aposta_snapshot_parser.parse_json(text)
    return aposta_snapshot_parser.parse_csv(text)


def normalized_key(row: dict, batch_id: int) -> str:
    payload = [
        batch_id,
        row.get("sport"),
        row.get("competition"),
        str(row.get("event_date")),
        row.get("team_a"),
        row.get("team_b"),
        row.get("market_text"),
        str(row.get("line")),
        row.get("selection"),
        str(row.get("odds_decimal")),
        "Aposta.LA",
    ]
    return (
        "aposta:"
        + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:32]
    )


def store_row(
    session: Session, batch: ManualImportBatch, row: dict
) -> tuple[ImportedOdds, bool]:
    market_id, market_code = map_market(session, row["sport"], row["market_text"])
    if not market_code:
        market_code = row.get("market_code", "")
    event_date = row.get("event_date")
    if isinstance(event_date, str) and event_date:
        try:
            from datetime import datetime as dt

            event_date = dt.fromisoformat(event_date)
        except ValueError:
            event_date = None
    mapping_status = "mapped" if market_id or market_code else "unmapped"
    odd = ImportedOdds(
        batch_id=batch.id,
        sport=row["sport"],
        bookmaker="Aposta.LA",
        competition=row.get("competition"),
        event_date=event_date,
        team_a=row.get("team_a"),
        team_b=row.get("team_b"),
        market_text=row["market_text"],
        market_id=market_id,
        market_code=market_code,
        line=row.get("line"),
        selection=row.get("selection"),
        odds_decimal=row["odds_decimal"],
        normalized_key=normalized_key(row, batch.id),
        source_name="aposta_la",
        is_current=True,
        captured_at=now(),
        event_date_sort=event_date.isoformat()
        if hasattr(event_date, "isoformat")
        else (str(event_date) if event_date else None),
        event_date_raw=row.get("event_date_raw"),
        event_time_status=row.get("event_time_status") or "unconfirmed",
        market_mapping_status=mapping_status,
    )
    session.add(odd)
    session.commit()
    session.refresh(odd)
    return odd, market_id is not None


def mirror_aposta_tables(
    session: Session, odds: list[ImportedOdds], run: ApostaSyncRun
) -> None:
    for sel in session.exec(select(ApostaSelection)).all():
        sel.is_active = False
        session.add(sel)
    session.commit()
    event_cache = {}
    market_cache = {}
    for odd in odds:
        event_key = "|".join(
            [
                odd.sport or "",
                odd.competition or "",
                odd.team_a or "",
                odd.team_b or "",
                str(odd.event_date or ""),
            ]
        )
        event = event_cache.get(event_key)
        if event is None:
            event = ApostaEvent(
                sport=odd.sport,
                competition=odd.competition,
                team_a=odd.team_a,
                team_b=odd.team_b,
                event_name=" vs ".join([p for p in [odd.team_a, odd.team_b] if p]),
                start_time=odd.event_date,
                external_id=f"run-{run.id}-{len(event_cache) + 1}",
                status="active",
            )
            session.add(event)
            session.commit()
            session.refresh(event)
            event_cache[event_key] = event
        market_key = (
            event_key + "|" + (odd.market_text or "") + "|" + str(odd.line or "")
        )
        market = market_cache.get(market_key)
        if market is None:
            market = ApostaMarket(
                event_id=event.id,
                market_text=odd.market_text,
                market_id=odd.market_id,
                market_code=odd.market_code,
                line=odd.line,
                is_mapped=odd.market_id is not None,
                source_status="current",
            )
            session.add(market)
            session.commit()
            session.refresh(market)
            market_cache[market_key] = market
        session.add(
            ApostaSelection(
                market_id=market.id,
                selection_text=odd.selection or "",
                selection_normalized=odd.selection,
                odds_decimal=odd.odds_decimal,
                implied_probability=1.0 / odd.odds_decimal
                if odd.odds_decimal
                else None,
                is_active=True,
            )
        )
    session.commit()


def latest_aposta_batch(session: Session) -> ManualImportBatch | None:
    return session.exec(
        select(ManualImportBatch)
        .where(
            ManualImportBatch.import_type == "aposta_odds",
            ManualImportBatch.status.in_(["success", "partial"]),
        )
        .order_by(ManualImportBatch.id.desc())
    ).first()


def current_odds(
    session: Session, include_stale: bool = False, include_past: bool = False
) -> list[ImportedOdds]:
    mark_expired(session)
    if include_stale:
        return snapshot_current_odds(session, include_stale=True)
    odds = snapshot_current_odds(session)
    if include_past:
        return odds
    return filter_current_odds(odds)


def run_event_matching_on_batch(session: Session, batch_id: int) -> dict:
    odds = session.exec(
        select(ImportedOdds).where(ImportedOdds.batch_id == batch_id)
    ).all()
    matched = 0
    high_confidence = 0
    for odd in odds:
        result = match_and_store(session, odd)
        if result.get("match_confidence", 0.0) >= 0.30:
            matched += 1
        if result.get("match_confidence", 0.0) >= 0.70:
            high_confidence += 1
    session.commit()
    return {
        "total": len(odds),
        "matched": matched,
        "high_confidence": high_confidence,
    }


def sync(session: Session, force_refresh: bool = False) -> dict:
    run = ApostaSyncRun(status="running", requested_by="dashboard")
    session.add(run)
    session.commit()
    session.refresh(run)
    warnings = []
    imported = []
    import_dir, archive_dir, error_dir = _import_paths()

    try:
        mode, sources = load_snapshot()

        if mode == "manual_required" or not sources:
            run.status = "manual_required"
            run.finished_at = now()
            run.message = "Colocar CSV en /opt/pirapire/data/imports/aposta o configurar APOSTA_BROWSER_WORKER_URL."
            session.add(run)
            session.commit()
            session.refresh(run)
            return {
                "run": run,
                "imported": 0,
                "mapped": 0,
                "unmapped": 0,
                "matched_events": 0,
                "current_odds": len(current_odds(session)),
                "expired_odds": len(snapshot_expired_odds(session)),
                "warnings": [run.message],
            }

        mark_expired(session)

        batch = ManualImportBatch(
            sport="mixed", import_type="aposta_odds", filename=f"aposta_run_{run.id}"
        )
        session.add(batch)
        session.commit()
        session.refresh(batch)

        mapped = 0
        unmapped = 0
        parsed_rows = 0
        failed_files = []
        success_files = []

        for name, text, file_path in sources:
            try:
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
                if file_path and file_path.exists():
                    try:
                        dest = archive_dir / file_path.name
                        shutil.move(str(file_path), str(dest))
                        success_files.append(file_path.name)
                    except Exception:
                        pass
            except Exception as e:
                failed_files.append(name)
                warnings.append(f"Error processing {name}: {e}")
                if file_path and file_path.exists():
                    try:
                        dest = error_dir / file_path.name
                        shutil.move(str(file_path), str(dest))
                    except Exception:
                        pass

        batch.imported_rows = len(imported)
        batch.total_rows = parsed_rows + len(warnings)
        batch.error_rows = len(warnings)
        if not imported and not success_files:
            batch.status = "error" if failed_files else "partial"
            batch.message = f"No se pudieron importar cuotas desde {mode}"
            if failed_files:
                batch.message += f"; archivos con error: {', '.join(failed_files[:5])}"
        else:
            batch.status = (
                "success"
                if imported and not warnings
                else ("partial" if imported else "error")
            )
            batch.message = f"{len(imported)} Aposta.LA odds imported from {mode}"
            if success_files:
                batch.message += f"; {len(success_files)} archivos procesados"

        batch.finished_at = now()
        session.add(batch)

        set_current_batch(session, batch.id)

        match_result = run_event_matching_on_batch(session, batch.id)

        current_imported = filter_current_odds(imported)
        past_imported = len(imported) - len(current_imported)
        mirror_aposta_tables(session, current_imported, run)

        run.status = batch.status
        run.finished_at = now()
        run.captured_responses = len(sources)
        run.parsed_events = len(
            {(o.sport, o.team_a, o.team_b, o.event_date) for o in imported}
        )
        run.parsed_markets = len({(o.market_text, o.line) for o in imported})
        run.parsed_selections = len(imported)
        run.mapped_markets = mapped
        run.unmapped_markets = unmapped
        run.error_count = len(warnings)
        run.message = batch.message
        if past_imported:
            run.message += f"; {past_imported} cuotas vencidas quedan solo como historial/estadistica"
        if match_result.get("matched", 0) > 0:
            run.message += f"; {match_result['matched']}/{match_result['total']} odds matched to events"

        session.add(run)
        session.commit()
        session.refresh(run)

        return {
            "run": run,
            "imported": len(imported),
            "mapped": mapped,
            "unmapped": unmapped,
            "matched_events": match_result.get("matched", 0),
            "high_confidence_matches": match_result.get("high_confidence", 0),
            "current_odds": len(current_odds(session)),
            "expired_odds": len(snapshot_expired_odds(session)),
            "files_processed": len(success_files),
            "files_failed": len(failed_files),
            "warnings": warnings,
        }
    except Exception as exc:
        run.status = "error"
        run.finished_at = now()
        run.error_count = 1
        run.message = str(exc)
        session.add(run)
        session.commit()
        session.refresh(run)
        return {
            "run": run,
            "imported": 0,
            "mapped": 0,
            "unmapped": 0,
            "matched_events": 0,
            "current_odds": len(current_odds(session)),
            "expired_odds": len(snapshot_expired_odds(session)),
            "files_processed": 0,
            "files_failed": 0,
            "warnings": [str(exc)],
        }


def match_summary(session: Session, odds: list[ImportedOdds]) -> tuple[int, int]:
    matched = 0
    for odd in odds:
        if (
            odd.is_matched
            and odd.match_confidence
            and odd.match_confidence >= settings.recommender_min_match_confidence
        ):
            matched += 1
    return matched, max(0, len(odds) - matched)
