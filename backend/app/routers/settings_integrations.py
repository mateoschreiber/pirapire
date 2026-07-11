"""Authenticated integration credential administration API."""

import json
from datetime import UTC, datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, SecretStr
from sqlalchemy import func
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models_sources import IntegrationAudit, IntegrationCredential, IntegrationProviderState
from ..models_football import FootballEntityMetadata, FootballMatch, FootballPlayer, FootballTeam
from ..models_imports import ImportedOdds
from ..models_lol import LolChampion, LolGameHistory, LolPlayerGameStat, RiotMatchReference, RiotPlayerIdentity
from ..services.config_auth import (
    COOKIE_NAME,
    check_rate_limit,
    client_ip,
    create_session,
    login_csrf,
    require_admin,
    require_csrf,
    verify_login_csrf,
    verify_origin,
    verify_password,
)
from ..services.integration_registry import ENV_FALLBACKS, get_provider, public_catalog
from ..services.integration_tester import test_candidate
from ..services.secret_provider import (
    SecretProvider,
    SecretStoreError,
    audit,
    decrypt_value,
    encrypt_value,
)

router = APIRouter(prefix="/api/settings", tags=["settings"])


class LoginPayload(BaseModel):
    password: SecretStr
    csrf_token: str


class CredentialPayload(BaseModel):
    value: SecretStr
    key_type: Literal["development", "personal"] | None = None
    default_platform: str | None = None
    regional_routes: list[str] | None = None


class RiskAcceptancePayload(BaseModel):
    reason: Literal["user_explicitly_accepted_known_credential"] = (
        "user_explicitly_accepted_known_credential"
    )


RIOT_PLATFORMS = {
    "br1", "eun1", "euw1", "jp1", "kr", "la1", "la2", "na1", "oc1", "ph2",
    "ru", "sg2", "th2", "tr1", "tw2", "vn2",
}
RIOT_REGIONS = {"americas", "asia", "europe", "sea"}


def _admin(request: Request):
    return require_admin(request)


def _actor(request: Request) -> str:
    return f"config-admin@{client_ip(request)}"


def _credential_contract(provider_slug: str, credential_name: str) -> dict:
    provider = get_provider(provider_slug)
    if not provider:
        raise HTTPException(status_code=404, detail="provider_not_found")
    if not provider["secret_fields"]:
        raise HTTPException(status_code=409, detail="provider_requires_no_key")
    if credential_name not in provider["secret_fields"]:
        raise HTTPException(status_code=404, detail="credential_not_found")
    return provider


def _count(session: Session, model, *conditions) -> int:
    query = select(func.count()).select_from(model)
    if conditions:
        query = query.where(*conditions)
    return int(session.exec(query).one())


def _coverage(session: Session, slug: str) -> dict:
    if slug == "football_data_org":
        return {
            "teams": _count(session, FootballTeam, FootballTeam.source_name == slug),
            "matches": _count(session, FootballMatch, FootballMatch.source_name == slug),
            "players": _count(session, FootballPlayer, FootballPlayer.source_name == slug),
        }
    if slug == "thesportsdb":
        return {"metadata": _count(session, FootballEntityMetadata, FootballEntityMetadata.source_name == slug)}
    if slug == "riot_api":
        return {
            "confirmed_identities": _count(session, RiotPlayerIdentity, RiotPlayerIdentity.confirmed.is_(True)),
            "personal_matches": _count(session, RiotMatchReference),
        }
    if slug == "leaguepedia":
        return {
            "pro_games": _count(session, LolGameHistory, LolGameHistory.source_name == "leaguepedia"),
            "player_rows": _count(session, LolPlayerGameStat, LolPlayerGameStat.source_name == "leaguepedia"),
        }
    if slug == "riot_datadragon":
        return {"champions": _count(session, LolChampion, LolChampion.source_name == "riot_datadragon")}
    if slug == "oracles_elixir":
        return {"pro_games": _count(session, LolGameHistory, LolGameHistory.source_name == "oracles_elixir")}
    if slug == "aposta_kambi":
        return {"odds_rows": _count(session, ImportedOdds, ImportedOdds.source_name == "aposta_la")}
    return {}


@router.get("/auth/bootstrap")
def auth_bootstrap(request: Request) -> dict:
    return {"csrf_token": login_csrf(request)}


@router.post("/auth/login")
def auth_login(payload: LoginPayload, request: Request, response: Response) -> dict:
    verify_origin(request)
    verify_login_csrf(request, payload.csrf_token)
    check_rate_limit(request, "config-login", settings.config_login_rate_limit)
    if not verify_password(payload.password.get_secret_value()):
        raise HTTPException(status_code=401, detail="invalid_admin_credentials")
    token, session = create_session(_actor(request))
    response.set_cookie(
        COOKIE_NAME,
        token,
        httponly=True,
        samesite="strict",
        secure=request.url.scheme == "https",
        max_age=settings.config_session_ttl_seconds,
        path="/api/settings",
    )
    return {"authenticated": True, "csrf_token": session.csrf_token}


@router.get("/auth/status")
def auth_status(request: Request) -> dict:
    try:
        admin = require_admin(request)
    except HTTPException:
        return {"authenticated": False}
    return {"authenticated": True, "csrf_token": admin.csrf_token}


@router.post("/auth/logout")
def auth_logout(request: Request, response: Response, admin=Depends(_admin)) -> dict:
    require_csrf(request, admin)
    response.delete_cookie(COOKIE_NAME, path="/api/settings")
    return {"authenticated": False}


@router.get("/integrations")
def list_integrations(
    session: Session = Depends(get_session), admin=Depends(_admin)
) -> dict:
    providers = []
    for item in public_catalog():
        item["coverage"] = _coverage(session, item["slug"])
        provider_state = session.exec(
            select(IntegrationProviderState).where(
                IntegrationProviderState.provider_slug == item["slug"]
            )
        ).first()
        item["operational_state"] = {
            "status": provider_state.status,
            "last_error_code": provider_state.last_error_code,
            "last_checked_at": provider_state.last_checked_at,
            "last_success_at": provider_state.last_success_at,
            "request_count": provider_state.request_count,
            "records_processed": provider_state.records_processed,
        } if provider_state else None
        credentials = []
        for name in item["credential_names"]:
            row = session.exec(
                select(IntegrationCredential).where(
                    IntegrationCredential.provider_slug == item["slug"],
                    IntegrationCredential.credential_name == name,
                )
            ).first()
            try:
                _, source = SecretProvider.get_secret(
                    item["slug"], name, session=session
                )
            except SecretStoreError as exc:
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            env_name = ENV_FALLBACKS.get((item["slug"], name))
            env_value = getattr(settings, env_name, "") if env_name else ""
            last4 = row.last4 if row else (env_value[-4:] if env_value else None)
            latest_test = session.exec(
                select(IntegrationAudit)
                .where(
                    IntegrationAudit.provider_slug == item["slug"],
                    IntegrationAudit.operation == "test_candidate",
                )
                .order_by(IntegrationAudit.created_at.desc())
            ).first()
            credentials.append(
                {
                    "name": name,
                    "configured": source != "unconfigured",
                    "source": source,
                    "last4": last4,
                    "tested_at": row.tested_at if row else None,
                    "test_status": row.test_status
                    if row
                    else ("legacy_env" if env_value else "unconfigured"),
                    "last_used_at": row.last_used_at if row else None,
                    "error_code": row.last_error_code if row else None,
                    "latest_test_at": latest_test.created_at if latest_test else None,
                    "latest_test_result": latest_test.result if latest_test else None,
                    "latest_test_error_code": latest_test.detail_code
                    if latest_test
                    else None,
                    "risk_accepted": bool(
                        row and row.test_status == "active_accepted_risk"
                    ),
                    "accepted_risk_at": row.accepted_risk_at if row else None,
                    "key_type": row.key_type if row else None,
                    "default_platform": row.default_platform if row else None,
                    "regional_routes": json.loads(row.regional_routes)
                    if row and row.regional_routes
                    else [],
                    "expires_at": row.expires_at if row else None,
                }
            )
        item["credentials"] = credentials
        providers.append(item)
    return {"providers": providers}


@router.post("/integrations/{provider_slug}/test")
def test_integration(
    provider_slug: str,
    payload: CredentialPayload,
    request: Request,
    credential_name: str = "api_key",
    session: Session = Depends(get_session),
    admin=Depends(_admin),
) -> dict:
    require_csrf(request, admin)
    check_rate_limit(request, "integration-test", settings.config_test_rate_limit)
    _credential_contract(provider_slug, credential_name)
    result = test_candidate(
        provider_slug, credential_name, payload.value.get_secret_value()
    )
    audit(
        session,
        provider_slug,
        "test_candidate",
        result["status"],
        admin.actor,
        result["error_code"],
    )
    session.commit()
    if not result["ok"]:
        status_code = (
            422
            if result["error_code"] in {"invalid_candidate", "invalid_credential", "invalid_key", "expired_key", "forbidden"}
            else 502
        )
        raise HTTPException(status_code=status_code, detail=result["error_code"])
    return {"ok": True, "status": "success"}


@router.put("/integrations/{provider_slug}/credentials/{credential_name}")
def put_credential(
    provider_slug: str,
    credential_name: str,
    payload: CredentialPayload,
    request: Request,
    session: Session = Depends(get_session),
    admin=Depends(_admin),
) -> dict:
    require_csrf(request, admin)
    check_rate_limit(request, "integration-test", settings.config_test_rate_limit)
    _credential_contract(provider_slug, credential_name)
    candidate = payload.value.get_secret_value()
    result = test_candidate(provider_slug, credential_name, candidate)
    if not result["ok"]:
        audit(
            session,
            provider_slug,
            "rotate",
            "failed",
            admin.actor,
            result["error_code"],
        )
        session.commit()
        status_code = (
            422
            if result["error_code"] in {"invalid_candidate", "invalid_credential", "invalid_key", "expired_key", "forbidden"}
            else 502
        )
        raise HTTPException(status_code=status_code, detail=result["error_code"])
    now = datetime.now(UTC)
    row = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.provider_slug == provider_slug,
            IntegrationCredential.credential_name == credential_name,
        )
    ).first()
    operation = "rotate" if row else "create"
    if row is None:
        row = IntegrationCredential(
            provider_slug=provider_slug,
            credential_name=credential_name,
            encrypted_value="",
            last4="",
            configured_at=now,
        )
    row.encrypted_value = encrypt_value(candidate)
    row.last4 = candidate[-4:]
    row.updated_at = now
    row.tested_at = now
    row.test_status = "success"
    row.last_error_code = None
    row.accepted_risk_at = None
    row.accepted_by = None
    row.accepted_reason = None
    if provider_slug == "riot_api":
        key_type = payload.key_type or "development"
        platform = payload.default_platform or "la2"
        routes = payload.regional_routes or ["americas"]
        if platform not in RIOT_PLATFORMS or not routes or not set(routes) <= RIOT_REGIONS:
            raise HTTPException(status_code=400, detail="invalid_riot_metadata")
        row.key_type = key_type
        row.default_platform = platform
        row.regional_routes = json.dumps(sorted(set(routes)))
        row.expires_at = now + timedelta(hours=24) if key_type == "development" else None
    else:
        row.key_type = None
        row.default_platform = None
        row.regional_routes = None
        row.expires_at = None
    session.add(row)
    audit(session, provider_slug, operation, "success", admin.actor)
    session.commit()
    SecretProvider.invalidate(provider_slug)
    return {
        "configured": True,
        "source": "ui",
        "last4": row.last4,
        "tested_at": row.tested_at,
        "test_status": row.test_status,
    }


@router.post(
    "/integrations/{provider_slug}/credentials/{credential_name}/accept-risk"
)
def accept_credential_risk(
    provider_slug: str,
    credential_name: str,
    payload: RiskAcceptancePayload,
    request: Request,
    session: Session = Depends(get_session),
    admin=Depends(_admin),
) -> dict:
    """Activate an existing encrypted override after explicit administrator consent."""
    require_csrf(request, admin)
    check_rate_limit(request, "integration-test", settings.config_test_rate_limit)
    _credential_contract(provider_slug, credential_name)
    if provider_slug != "football_data_org":
        raise HTTPException(status_code=409, detail="risk_acceptance_not_supported")
    row = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.provider_slug == provider_slug,
            IntegrationCredential.credential_name == credential_name,
        )
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="ui_override_not_found")
    try:
        candidate = decrypt_value(row.encrypted_value)
    except SecretStoreError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    result = test_candidate(provider_slug, credential_name, candidate)
    candidate = ""
    if not result["ok"]:
        audit(
            session,
            provider_slug,
            "accept_risk",
            "failed",
            admin.actor,
            result["error_code"],
        )
        session.commit()
        raise HTTPException(status_code=422, detail=result["error_code"])
    now = datetime.now(UTC)
    row.test_status = "active_accepted_risk"
    row.tested_at = now
    row.updated_at = now
    row.last_error_code = None
    row.accepted_risk_at = now
    row.accepted_by = admin.actor
    row.accepted_reason = payload.reason
    session.add(row)
    audit(session, provider_slug, "accept_risk", "success", admin.actor, "explicit_user_decision")
    session.commit()
    return {
        "configured": True,
        "source": "ui",
        "status": "active_accepted_risk",
        "accepted_risk_at": row.accepted_risk_at,
    }


@router.delete("/integrations/{provider_slug}/credentials/{credential_name}")
def delete_credential(
    provider_slug: str,
    credential_name: str,
    request: Request,
    session: Session = Depends(get_session),
    admin=Depends(_admin),
) -> dict:
    require_csrf(request, admin)
    _credential_contract(provider_slug, credential_name)
    row = session.exec(
        select(IntegrationCredential).where(
            IntegrationCredential.provider_slug == provider_slug,
            IntegrationCredential.credential_name == credential_name,
        )
    ).first()
    if not row:
        raise HTTPException(status_code=404, detail="ui_override_not_found")
    session.delete(row)
    audit(session, provider_slug, "delete_override", "success", admin.actor)
    session.commit()
    SecretProvider.invalidate(provider_slug)
    _, source = SecretProvider.get_secret(
        provider_slug, credential_name, session=session
    )
    return {"deleted": True, "source": source, "env_fallback": source == "env"}
