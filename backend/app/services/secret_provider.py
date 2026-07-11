"""Encrypted integration credential storage with UI-to-env precedence."""

from __future__ import annotations

import os
import secrets
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken
from sqlmodel import Session, select

from ..config import settings
from ..database import engine
from ..models_sources import IntegrationAudit, IntegrationCredential
from .integration_registry import ENV_FALLBACKS, get_provider

ACTIVE_STATUSES = ("success", "active_accepted_risk")

class SecretStoreError(RuntimeError):
    pass


def _ensure_secret_file(path_value: str, generator) -> bytes:
    path = Path(path_value)
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(path.parent, 0o700)
    try:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(fd, "wb") as handle:
            handle.write(generator())
    os.chmod(path, 0o600)
    return path.read_bytes().strip()


def ensure_runtime_secrets() -> None:
    _ensure_secret_file(settings.integration_master_key_path, Fernet.generate_key)
    _ensure_secret_file(
        settings.config_admin_password_path,
        lambda: secrets.token_urlsafe(24).encode(),
    )
    _ensure_secret_file(
        settings.config_session_key_path,
        lambda: secrets.token_bytes(32).hex().encode(),
    )


def _fernet() -> Fernet:
    try:
        key = Path(settings.integration_master_key_path).read_bytes().strip()
        return Fernet(key)
    except Exception as exc:
        raise SecretStoreError("master_key_unavailable") from exc


def encrypt_value(value: str) -> str:
    if not value:
        raise ValueError("empty_credential")
    return _fernet().encrypt(value.encode()).decode()


def decrypt_value(token: str) -> str:
    try:
        return _fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise SecretStoreError("credential_decryption_failed") from exc


def audit(
    session: Session,
    provider_slug: str,
    operation: str,
    result: str,
    actor: str,
    detail_code: str | None = None,
) -> None:
    session.add(
        IntegrationAudit(
            provider_slug=provider_slug,
            operation=operation,
            result=result,
            actor=actor,
            detail_code=detail_code,
        )
    )


class SecretProvider:
    """Resolve on every call; there is deliberately no process-local secret cache."""

    @staticmethod
    def get_secret(
        provider_slug: str,
        credential_name: str,
        session: Session | None = None,
        mark_used: bool = False,
    ) -> tuple[str | None, str]:
        provider = get_provider(provider_slug)
        if not provider or credential_name not in provider["secret_fields"]:
            return None, "unconfigured"
        owns_session = session is None
        db = session or Session(engine)
        try:
            row = db.exec(
                select(IntegrationCredential).where(
                    IntegrationCredential.provider_slug == provider_slug,
                    IntegrationCredential.credential_name == credential_name,
                    IntegrationCredential.test_status.in_(ACTIVE_STATUSES),
                )
            ).first()
            if row:
                if row.expires_at is not None:
                    expires_at = row.expires_at
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=UTC)
                    if expires_at <= datetime.now(UTC):
                        row.test_status = "expired"
                        row.last_error_code = "expired_key"
                        db.add(row)
                        db.commit()
                        row = None
            if row:
                value = decrypt_value(row.encrypted_value)
                if mark_used:
                    row.last_used_at = datetime.now(UTC)
                    db.add(row)
                    db.commit()
                return value, "ui"
            setting_name = ENV_FALLBACKS.get((provider_slug, credential_name))
            value = (
                os.environ.get(setting_name.upper(), "")
                or getattr(settings, setting_name, "")
                if setting_name
                else ""
            )
            if value:
                return value, "env"
            public_default = provider.get("public_default_value", "")
            if public_default:
                return public_default, "public_free"
            return None, "unconfigured"
        finally:
            if owns_session:
                db.close()

    @staticmethod
    def ui_override_exists(
        provider_slug: str, credential_name: str, session: Session
    ) -> bool:
        return (
            session.exec(
                select(IntegrationCredential.id).where(
                    IntegrationCredential.provider_slug == provider_slug,
                    IntegrationCredential.credential_name == credential_name,
                    IntegrationCredential.test_status.in_(ACTIVE_STATUSES),
                )
            ).first()
            is not None
        )

    @staticmethod
    def invalidate(provider_slug: str | None = None) -> None:
        return None
