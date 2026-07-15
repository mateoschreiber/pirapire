"""Shared httpx wrapper for all external API calls."""

import logging

import httpx

from ..config import settings

logger = logging.getLogger("pirapire.http")

_client: httpx.Client | None = None


def get_client() -> httpx.Client:
    global _client
    if _client is None:
        _client = httpx.Client(
            timeout=httpx.Timeout(
                connect=settings.http_timeout_connect,
                read=settings.http_timeout_read,
                write=settings.http_timeout_write,
                pool=settings.http_timeout_pool,
            ),
            headers={"User-Agent": "PirapireLocal/1.0"},
            transport=httpx.HTTPTransport(retries=2),
        )
    return _client


def safe_get(url: str, headers: dict | None = None) -> httpx.Response | None:
    try:
        client = get_client()
        response = client.get(url, headers=headers)
        response.raise_for_status()
        return response
    except httpx.TimeoutException:
        logger.warning("Timeout fetching %s", url)
    except httpx.HTTPStatusError as e:
        logger.warning("HTTP %s fetching %s", e.response.status_code, url)
    except httpx.RequestError as e:
        logger.warning("Request error fetching %s: %s", url, e)
    return None


def safe_get_json(url: str, headers: dict | None = None):
    response = safe_get(url, headers)
    if response is None:
        return None
    try:
        return response.json()
    except Exception as e:
        logger.warning("JSON parse error for %s: %s", url, e)
        return None


def request_json(url: str, headers: dict | None = None) -> dict:
    """Fetch JSON returning a structured result (never raises).

    Returns {"ok": bool, "status": int|None, "data": any, "error": str|None}.
    """
    try:
        client = get_client()
        response = client.get(url, headers=headers)
        status = response.status_code
        response.raise_for_status()
        return {"ok": True, "status": status, "data": response.json(), "error": None, "retry_after": None}
    except httpx.HTTPStatusError as e:
        retry_after = None
        if e.response.status_code == 429:
            retry_after = e.response.headers.get("Retry-After")
        return {
            "ok": False,
            "status": e.response.status_code,
            "data": None,
            "error": f"HTTP {e.response.status_code}",
            "retry_after": retry_after,
        }
    except httpx.TimeoutException:
        return {"ok": False, "status": None, "data": None, "error": "timeout", "retry_after": None}
    except httpx.RequestError as e:
        return {
            "ok": False,
            "status": None,
            "data": None,
            "error": f"request_error: {type(e).__name__}",
            "retry_after": None,
        }
    except Exception as e:
        return {
            "ok": False,
            "status": None,
            "data": None,
            "error": f"parse_error: {type(e).__name__}",
            "retry_after": None,
        }

