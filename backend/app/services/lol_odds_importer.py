import csv
import os
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import update
from sqlmodel import Session, select

from ..models_lol import LolMatchEvent, LolOddsSnapshot, LolTeamOdd
from .lol_team_aliases import resolve_team_alias


def _now():
    return datetime.now(timezone.utc)


def _captured(value: str) -> datetime:
    if not value:
        return _now()
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"captured_at inválido: {value}") from exc
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def import_odds_csv(session: Session, filepath: str):
    grouped = defaultdict(list)
    with open(filepath, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        required = {"match_key", "team_name", "decimal_odds"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Faltan columnas requeridas: {', '.join(sorted(missing))}")
        for row_number, row in enumerate(reader, start=2):
            match_key = (row.get("match_key") or "").strip()
            team_name = (row.get("team_name") or "").strip()
            odds_text = (row.get("decimal_odds") or "").strip()
            provider = (row.get("provider") or "manual").strip()
            if not match_key or not team_name or not odds_text:
                raise ValueError(f"Fila {row_number}: match_key, team_name y decimal_odds son obligatorios")
            try:
                decimal_odds = float(odds_text)
            except ValueError as exc:
                raise ValueError(f"Fila {row_number}: decimal_odds inválido") from exc
            if decimal_odds <= 1.0:
                raise ValueError(f"Fila {row_number}: decimal_odds debe ser mayor a 1.0")
            captured_at = _captured((row.get("captured_at") or "").strip())
            grouped[(match_key, provider, captured_at)].append((row_number, team_name, decimal_odds))

    inserted = 0
    for (match_key, provider, captured_at), selections in grouped.items():
        match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
        if not match:
            raise ValueError(f"No existe el partido match_key={match_key}")
        resolved_selections = []
        seen = set()
        for row_number, team_name, decimal_odds in selections:
            resolved = resolve_team_alias(session, team_name) or team_name
            if resolved not in (match.team_a, match.team_b):
                raise ValueError(f"Fila {row_number}: {team_name} no pertenece a {match.team_a} vs {match.team_b}")
            if resolved in seen:
                raise ValueError(f"Fila {row_number}: cuota duplicada para {resolved}")
            seen.add(resolved)
            resolved_selections.append((resolved, decimal_odds))

        session.exec(
            update(LolOddsSnapshot)
            .where(LolOddsSnapshot.match_event_id == match.id)
            .where(LolOddsSnapshot.provider == provider)
            .where(LolOddsSnapshot.is_current == True)  # noqa: E712
            .values(is_current=False)
        )
        snapshot = LolOddsSnapshot(
            match_event_id=match.id,
            provider=provider,
            captured_at=captured_at,
            is_current=True,
            source_url=filepath,
        )
        session.add(snapshot)
        session.flush()
        for team_name, decimal_odds in resolved_selections:
            session.add(LolTeamOdd(snapshot_id=snapshot.id, team_name=team_name, decimal_odds=decimal_odds))
            inserted += 1
    session.commit()
    return {"inserted": inserted, "file": filepath, "snapshots": len(grouped)}


def import_odds_directory(session: Session, directory: str = None):
    if directory is None:
        from ..config import settings
        directory = settings.lol_odds_import_dir
    inbox = os.path.join(directory, "inbox") if not directory.endswith("inbox") else directory
    processed_dir = os.path.join(directory, "processed")
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)
    total = 0
    for filename in sorted(os.listdir(inbox)):
        if not filename.endswith(".csv"):
            continue
        source = os.path.join(inbox, filename)
        result = import_odds_csv(session, source)
        total += result["inserted"]
        destination = os.path.join(processed_dir, filename)
        if os.path.exists(destination):
            os.remove(destination)
        os.rename(source, destination)
    return {"inserted": total}
