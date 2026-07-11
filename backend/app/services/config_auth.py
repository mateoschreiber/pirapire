"""Narrow administrative session for integration configuration only."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, Request

from ..config import settings

COOKIE_NAME = "pirapire_config_admin"
_attempts: dict[tuple[str, str], list[float]] = {}
_attempts_lock = threading.Lock()


@dataclass(frozen=True)
class AdminSession:
    actor: str
    csrf_token: str


def _key() -> bytes:
    return Path(settings.config_session_key_path).read_bytes().strip()


def _encode(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    body = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    signature = hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()
    return f"{body}.{signature}"


def _decode(token: str) -> dict:
    try:
        body, signature = token.rsplit(".", 1)
        expected = hmac.new(_key(), body.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        padded = body + "=" * (-len(body) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError
        return payload
    except Exception as exc:
        raise HTTPException(status_code=401, detail="admin_session_invalid") from exc


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def login_csrf(request: Request) -> str:
    return _encode(
        {
            "purpose": "login",
            "ip": client_ip(request),
            "exp": int(time.time()) + 600,
        }
    )


def verify_login_csrf(request: Request, token: str) -> None:
    try:
        payload = _decode(token)
    except HTTPException as exc:
        raise HTTPException(status_code=403, detail="csrf_invalid") from exc
    if payload.get("purpose") != "login" or payload.get("ip") != client_ip(request):
        raise HTTPException(status_code=403, detail="csrf_invalid")


def verify_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") != str(request.base_url).rstrip("/"):
        raise HTTPException(status_code=403, detail="origin_invalid")


def check_rate_limit(
    request: Request, bucket: str, limit: int, window: int = 60
) -> None:
    now = time.monotonic()
    key = (bucket, client_ip(request))
    with _attempts_lock:
        recent = [stamp for stamp in _attempts.get(key, []) if now - stamp < window]
        if len(recent) >= limit:
            raise HTTPException(status_code=429, detail="rate_limited")
        recent.append(now)
        _attempts[key] = recent


def verify_password(candidate: str) -> bool:
    expected = Path(settings.config_admin_password_path).read_text().strip()
    return hmac.compare_digest(candidate.encode(), expected.encode())


def create_session(actor: str) -> tuple[str, AdminSession]:
    csrf = (
        base64.urlsafe_b64encode(
            hashlib.sha256(f"{actor}:{time.time_ns()}".encode()).digest()
        )
        .decode()
        .rstrip("=")
    )
    session = AdminSession(actor=actor, csrf_token=csrf)
    token = _encode(
        {
            "purpose": "admin",
            "actor": actor,
            "csrf": csrf,
            "exp": int(time.time()) + settings.config_session_ttl_seconds,
        }
    )
    return token, session


def require_admin(request: Request) -> AdminSession:
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(status_code=401, detail="admin_auth_required")
    payload = _decode(token)
    if payload.get("purpose") != "admin":
        raise HTTPException(status_code=401, detail="admin_session_invalid")
    return AdminSession(actor=payload["actor"], csrf_token=payload["csrf"])


def require_csrf(request: Request, admin: AdminSession) -> None:
    verify_origin(request)
    supplied = request.headers.get("x-csrf-token", "")
    if not supplied or not hmac.compare_digest(supplied, admin.csrf_token):
        raise HTTPException(status_code=403, detail="csrf_invalid")
