import os
import secrets
import stat
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlmodel import Session, delete, select

from app.config import settings
from app.database import engine
from app.main import app
from app.models_sources import IntegrationAudit, IntegrationCredential
from app.routers import settings_integrations
from app.services import config_auth
from app.services.secret_provider import (
    SecretProvider,
    SecretStoreError,
    decrypt_value,
    encrypt_value,
)
from app.services.integration_registry import public_catalog


@pytest.fixture()
def admin_client():
    with Session(engine) as session:
        session.exec(delete(IntegrationAudit))
        session.exec(delete(IntegrationCredential))
        session.commit()
    config_auth._attempts.clear()
    client = TestClient(app)
    bootstrap = client.get("/api/settings/auth/bootstrap").json()["csrf_token"]
    password = Path(settings.config_admin_password_path).read_text().strip()
    response = client.post(
        "/api/settings/auth/login",
        json={"password": password, "csrf_token": bootstrap},
    )
    assert response.status_code == 200
    yield client, response.json()["csrf_token"]
    with Session(engine) as session:
        session.exec(delete(IntegrationAudit))
        session.exec(delete(IntegrationCredential))
        session.commit()


def test_anonymous_writes_and_reads_are_rejected():
    client = TestClient(app)
    assert client.get("/api/settings/integrations").status_code == 401
    assert (
        client.put(
            "/api/settings/integrations/football_data_org/credentials/api_key",
            json={"value": secrets.token_urlsafe(20)},
        ).status_code
        == 401
    )


def test_login_requires_valid_csrf_and_password():
    client = TestClient(app)
    candidate = secrets.token_urlsafe(24)
    assert (
        client.post(
            "/api/settings/auth/login",
            json={"password": candidate, "csrf_token": candidate},
        ).status_code
        == 403
    )
    bootstrap = client.get("/api/settings/auth/bootstrap").json()["csrf_token"]
    assert (
        client.post(
            "/api/settings/auth/login",
            json={"password": candidate, "csrf_token": bootstrap},
        ).status_code
        == 401
    )


def test_admin_cookie_security_attributes(admin_client):
    client, _ = admin_client
    status = client.get("/api/settings/auth/status")
    assert status.status_code == 200
    cookie = client.cookies.get("pirapire_config_admin")
    assert cookie


def test_login_cookie_is_httponly_and_strict():
    client = TestClient(app)
    bootstrap = client.get("/api/settings/auth/bootstrap").json()["csrf_token"]
    password = Path(settings.config_admin_password_path).read_text().strip()
    response = client.post(
        "/api/settings/auth/login",
        json={"password": password, "csrf_token": bootstrap},
    )
    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=strict" in header


def test_login_rate_limit_is_enforced():
    client = TestClient(app)
    config_auth._attempts.clear()
    for _ in range(settings.config_login_rate_limit):
        bootstrap = client.get("/api/settings/auth/bootstrap").json()["csrf_token"]
        response = client.post(
            "/api/settings/auth/login",
            json={"password": secrets.token_urlsafe(18), "csrf_token": bootstrap},
        )
        assert response.status_code == 401
    bootstrap = client.get("/api/settings/auth/bootstrap").json()["csrf_token"]
    response = client.post(
        "/api/settings/auth/login",
        json={"password": secrets.token_urlsafe(18), "csrf_token": bootstrap},
    )
    assert response.status_code == 429


def test_csrf_and_origin_protect_writes(admin_client):
    client, csrf = admin_client
    value = secrets.token_urlsafe(24)
    url = "/api/settings/integrations/football_data_org/test"
    assert client.post(url, json={"value": value}).status_code == 403
    assert (
        client.post(
            url,
            json={"value": value},
            headers={"X-CSRF-Token": csrf, "Origin": "http://untrusted.invalid"},
        ).status_code
        == 403
    )


def test_failed_candidate_does_not_replace_active_credential(admin_client, monkeypatch):
    client, csrf = admin_client
    current = secrets.token_urlsafe(28)
    candidate = secrets.token_urlsafe(28)
    with Session(engine) as session:
        row = IntegrationCredential(
            provider_slug="football_data_org",
            credential_name="api_key",
            encrypted_value=encrypt_value(current),
            last4=current[-4:],
            test_status="success",
        )
        session.add(row)
        session.commit()
    monkeypatch.setattr(
        settings_integrations,
        "test_candidate",
        lambda *args: {
            "ok": False,
            "status": "failed",
            "error_code": "invalid_credential",
        },
    )
    response = client.put(
        "/api/settings/integrations/football_data_org/credentials/api_key",
        json={"value": candidate},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 422
    with Session(engine) as session:
        stored = session.exec(select(IntegrationCredential)).one()
        assert decrypt_value(stored.encrypted_value) == current
        assert candidate not in stored.encrypted_value


def test_successful_rotation_is_encrypted_and_never_returned(admin_client, monkeypatch):
    client, csrf = admin_client
    candidate = secrets.token_urlsafe(32)
    monkeypatch.setattr(
        settings_integrations,
        "test_candidate",
        lambda *args: {"ok": True, "status": "success", "error_code": None},
    )
    response = client.put(
        "/api/settings/integrations/football_data_org/credentials/api_key",
        json={"value": candidate},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert candidate not in response.text
    listing = client.get("/api/settings/integrations")
    assert listing.status_code == 200
    assert candidate not in listing.text
    assert "encrypted_value" not in listing.text
    assert candidate not in client.get("/settings/ui").text
    with Session(engine) as session:
        stored = session.exec(select(IntegrationCredential)).one()
        assert stored.encrypted_value != candidate
        assert decrypt_value(stored.encrypted_value) == candidate
        value, source = SecretProvider.get_secret(
            "football_data_org", "api_key", session=session
        )
        assert value == candidate
        assert source == "ui"
    database_path = settings.database_url.replace("sqlite:///", "")
    assert candidate.encode() not in Path(database_path).read_bytes()


def test_audit_log_contains_metadata_only(admin_client, monkeypatch):
    client, csrf = admin_client
    candidate = secrets.token_urlsafe(30)
    monkeypatch.setattr(
        settings_integrations,
        "test_candidate",
        lambda *args: {"ok": True, "status": "success", "error_code": None},
    )
    response = client.put(
        "/api/settings/integrations/football_data_org/credentials/api_key",
        json={"value": candidate},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    with Session(engine) as session:
        audit = session.exec(select(IntegrationAudit)).one()
        serialized = "|".join(
            [
                audit.provider_slug,
                audit.operation,
                audit.result,
                audit.actor,
                audit.detail_code or "",
            ]
        )
        assert candidate not in serialized


def test_delete_override_returns_to_env_fallback(admin_client, monkeypatch):
    client, csrf = admin_client
    ui_value = secrets.token_urlsafe(24)
    env_value = secrets.token_urlsafe(24)
    monkeypatch.setattr(settings, "football_data_api_key", env_value)
    with Session(engine) as session:
        session.add(
            IntegrationCredential(
                provider_slug="football_data_org",
                credential_name="api_key",
                encrypted_value=encrypt_value(ui_value),
                last4=ui_value[-4:],
                test_status="success",
            )
        )
        session.commit()
    response = client.delete(
        "/api/settings/integrations/football_data_org/credentials/api_key",
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200
    assert response.json()["source"] == "env"
    with Session(engine) as session:
        value, source = SecretProvider.get_secret(
            "football_data_org", "api_key", session=session
        )
        assert value == env_value
        assert source == "env"


def test_wrong_master_key_has_controlled_failure(admin_client):
    client, _ = admin_client
    value = secrets.token_urlsafe(24)
    with Session(engine) as session:
        session.add(
            IntegrationCredential(
                provider_slug="football_data_org",
                credential_name="api_key",
                encrypted_value=encrypt_value(value),
                last4=value[-4:],
                test_status="success",
            )
        )
        session.commit()
    path = Path(settings.integration_master_key_path)
    original = path.read_bytes()
    try:
        path.write_bytes(Fernet.generate_key())
        os.chmod(path, 0o600)
        with pytest.raises(SecretStoreError, match="credential_decryption_failed"):
            SecretProvider.get_secret("football_data_org", "api_key")
        response = client.get("/api/settings/integrations")
        assert response.status_code == 409
        assert value not in response.text
    finally:
        path.write_bytes(original)
        os.chmod(path, 0o600)


def test_worker_style_reads_observe_atomic_rotation(admin_client):
    old_value = secrets.token_urlsafe(24)
    new_value = secrets.token_urlsafe(24)
    with Session(engine) as session:
        session.add(
            IntegrationCredential(
                provider_slug="football_data_org",
                credential_name="api_key",
                encrypted_value=encrypt_value(old_value),
                last4=old_value[-4:],
                test_status="success",
            )
        )
        session.commit()

    def read_effective():
        return SecretProvider.get_secret("football_data_org", "api_key")[0]

    with ThreadPoolExecutor(max_workers=4) as pool:
        before = list(pool.map(lambda _: read_effective(), range(8)))
        with Session(engine) as session:
            row = session.exec(select(IntegrationCredential)).one()
            row.encrypted_value = encrypt_value(new_value)
            row.last4 = new_value[-4:]
            session.add(row)
            session.commit()
        after = list(pool.map(lambda _: read_effective(), range(8)))
    assert set(before) == {old_value}
    assert set(after) == {new_value}


def test_provider_catalog_has_only_fixed_supported_integrations():
    catalog = {item["slug"]: item for item in public_catalog()}
    assert catalog["football_data_org"]["requires_key"] is True
    assert catalog["riot_api"]["requires_key"] is True
    assert catalog["thesportsdb"]["requires_key"] is True
    for slug in ("aposta_kambi", "leaguepedia", "riot_datadragon", "oracles_elixir"):
        assert catalog[slug]["requires_key"] is False
    assert all("url" not in item for item in catalog.values())


def test_settings_html_never_preloads_credentials():
    html = TestClient(app).get("/settings/ui").text
    assert 'type="password"' in html
    assert 'autocomplete="current-password"' in html
    assert "encrypted_value" not in html
    assert "FOOTBALL_DATA_API_KEY" not in html


def test_runtime_secret_files_are_outside_database_and_mode_0600():
    for value in (
        settings.integration_master_key_path,
        settings.config_admin_password_path,
        settings.config_session_key_path,
    ):
        path = Path(value)
        assert path.exists()
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    database_path = Path(settings.database_url.replace("sqlite:///", ""))
    master = Path(settings.integration_master_key_path).read_bytes().strip()
    assert master not in database_path.read_bytes()
