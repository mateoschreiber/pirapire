import csv, os, re
from datetime import datetime, timezone
from sqlmodel import Session, select
from ..models_lol import LolMatchEvent, LolOddsSnapshot, LolTeamOdd
from .lol_team_aliases import resolve_team_alias


def _now():
    return datetime.now(timezone.utc)


def import_odds_csv(session: Session, filepath: str):
    inserted = 0
    with open(filepath, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            match_key = (row.get("match_key") or "").strip()
            team_name = (row.get("team_name") or "").strip()
            odds_str = (row.get("decimal_odds") or "").strip()
            provider = (row.get("provider") or "manual").strip()
            captured_str = (row.get("captured_at") or "").strip()
            if not match_key or not team_name or not odds_str:
                continue
            try:
                odds = float(odds_str)
            except ValueError:
                continue
            if odds <= 1.0:
                continue
            captured = _now()
            if captured_str:
                try:
                    captured = datetime.fromisoformat(captured_str.replace("Z", "+00:00"))
                except ValueError:
                    pass
            match = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == match_key)).first()
            if not match:
                continue
            resolved = resolve_team_alias(session, team_name) or team_name
            if resolved not in (match.team_a, match.team_b):
                continue
            snapshot_stmt = select(LolOddsSnapshot).where(LolOddsSnapshot.match_event_id == match.id, LolOddsSnapshot.provider == provider, LolOddsSnapshot.is_current == True)  # noqa: E712
            snapshot = session.exec(snapshot_stmt).first()
            if not snapshot:
                session.exec(select(LolOddsSnapshot).where(LolOddsSnapshot.match_event_id == match.id, LolOddsSnapshot.provider == provider)).update({"is_current": False})
                snapshot = LolOddsSnapshot(match_event_id=match.id, provider=provider, captured_at=captured, is_current=True, source_url=filepath)
                session.add(snapshot)
                session.commit()
                session.refresh(snapshot)
            existing_odd = session.exec(select(LolTeamOdd).where(LolTeamOdd.snapshot_id == snapshot.id, LolTeamOdd.team_name == resolved)).first()
            if existing_odd:
                existing_odd.decimal_odds = odds
                session.add(existing_odd)
            else:
                session.add(LolTeamOdd(snapshot_id=snapshot.id, team_name=resolved, decimal_odds=odds))
            session.commit()
            inserted += 1
    return {"inserted": inserted, "file": filepath}


def import_odds_directory(session: Session, directory: str = None):
    if directory is None:
        from ..config import settings
        directory = settings.lol_odds_import_dir
    inbox = os.path.join(directory, "inbox") if not directory.endswith("inbox") else directory
    processed_dir = os.path.join(directory, "processed")
    os.makedirs(inbox, exist_ok=True)
    os.makedirs(processed_dir, exist_ok=True)
    total = 0
    if not os.path.isdir(inbox):
        return {"inserted": 0}
    for fname in os.listdir(inbox):
        if not fname.endswith(".csv"):
            continue
        fpath = os.path.join(inbox, fname)
        result = import_odds_csv(session, fpath)
        total += result["inserted"]
        os.rename(fpath, os.path.join(processed_dir, fname))
    return {"inserted": total}
