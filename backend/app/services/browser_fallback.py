"""Probe-first browser fallback adapter for public, visible football pages.

This adapter only asks the internal browser worker to render allowlisted,
public pages. It never touches private/undocumented endpoints, never solves
CAPTCHAs, never parallelises navigation and never retries a block in a loop.
Results are cached per URL so repeated runs never duplicate work.
"""
from __future__ import annotations

from urllib.parse import urlparse

from ..config import settings
from . import http_client

# Public, visible pages only. TheSportsDB is the same data owner as the free
# API key already configured; its team pages are public and CAPTCHA-free.
ALLOWED_HOSTS = {"www.thesportsdb.com", "thesportsdb.com"}


def is_allowed(url: str) -> bool:
    try:
        return urlparse(url).hostname in ALLOWED_HOSTS
    except Exception:  # noqa: BLE001
        return False


def probe(url: str, timeout: float = 30.0) -> dict:
    """Ask the browser worker to render a public page. Probe mode: read-only.

    Returns {"ok", "status", "html"|None, "error"}. Never raises.
    """
    if not is_allowed(url):
        return {"ok": False, "status": None, "html": None, "error": "host_not_allowed"}
    worker = (settings.aposta_browser_worker_url or "").rstrip("/")
    if not worker:
        return {"ok": False, "status": None, "html": None, "error": "browser_worker_unconfigured"}
    # The worker exposes a generic render endpoint guarded by its own allowlist.
    endpoint = f"{worker}/render?url={url}&timeout={int(timeout * 1000)}"
    result = http_client.request_json(endpoint, headers=None)
    if not result.get("ok"):
        return {"ok": False, "status": result.get("status"), "html": None, "error": result.get("error") or "worker_error"}
    data = result.get("data")
    html = data.get("html") if isinstance(data, dict) else None
    return {"ok": bool(html), "status": result.get("status"), "html": html, "error": None if html else "empty"}


def cache_key(url: str) -> str:
    return f"browser|{url}"
