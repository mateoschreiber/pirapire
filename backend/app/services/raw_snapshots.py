"""Create and deduplicate raw API payload snapshots."""

import hashlib

from sqlmodel import Session

from ..models_sources import RawSnapshot


def payload_hash(payload: dict | list | str) -> str:
    raw = payload if isinstance(payload, str) else json_serialize(payload)
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def json_serialize(payload: dict | list) -> str:
    import json

    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def save_snapshot(
    session: Session,
    run_id: int,
    source_slug: str,
    sport: str,
    data_type: str,
    payload: dict | list | str,
    external_id: str | None = None,
) -> tuple[RawSnapshot | None, bool]:
    """Save a RawSnapshot if not already present. Returns (snapshot, is_new)."""
    raw_json = payload if isinstance(payload, str) else json_serialize(payload)
    h = payload_hash(payload)

    from sqlmodel import select

    existing = session.exec(
        select(RawSnapshot).where(
            RawSnapshot.payload_hash == h, RawSnapshot.source_slug == source_slug
        )
    ).first()
    if existing is not None:
        return existing, False

    snap = RawSnapshot(
        run_id=run_id,
        source_slug=source_slug,
        sport=sport,
        data_type=data_type,
        external_id=external_id,
        payload_json=raw_json,
        payload_hash=h,
    )
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap, True
