"""Non-secret operational state shared by integration jobs and Config."""

import json
from datetime import UTC, datetime

from sqlmodel import Session, select

from ..models_sources import IntegrationProviderState


def record(
    session: Session,
    provider_slug: str,
    status: str,
    *,
    error_code: str | None = None,
    request_count: int = 0,
    records_processed: int = 0,
    coverage: dict | None = None,
) -> IntegrationProviderState:
    row = session.exec(
        select(IntegrationProviderState).where(
            IntegrationProviderState.provider_slug == provider_slug
        )
    ).first()
    row = row or IntegrationProviderState(provider_slug=provider_slug)
    now = datetime.now(UTC)
    row.status = status
    row.last_error_code = error_code
    row.last_checked_at = now
    if status == "success":
        row.last_success_at = now
    row.request_count = request_count
    row.records_processed = records_processed
    row.coverage_json = json.dumps(coverage or {}, sort_keys=True)
    session.add(row)
    session.commit()
    return row
