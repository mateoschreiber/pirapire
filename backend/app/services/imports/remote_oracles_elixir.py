"""Download and import an Oracle's Elixir-compatible CSV from a remote URL."""

import csv
import hashlib
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests
from sqlmodel import Session


class RemoteCsvError(ValueError):
    """The configured remote source did not return a usable CSV."""


def google_drive_download_url(url: str) -> str:
    """Turn a normal Google Drive share link into its direct-download URL."""
    parsed = urlparse(url.strip())
    if parsed.hostname not in {"drive.google.com", "www.drive.google.com"}:
        return url.strip()

    match = re.search(r"/file/d/([^/]+)", parsed.path)
    file_id = match.group(1) if match else parse_qs(parsed.query).get("id", [""])[0]
    if not file_id:
        raise RemoteCsvError("No se encontró el ID del archivo en el enlace de Google Drive")
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"


def _validate_csv(path: Path) -> None:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        fieldnames = csv.DictReader(stream).fieldnames or []
    headers = {name.strip().lower().replace(" ", "").replace("_", "") for name in fieldnames}
    required = {"gameid", "position", "teamname"}
    if not required.issubset(headers):
        missing = ", ".join(sorted(required - headers))
        raise RemoteCsvError(f"El archivo remoto no tiene las columnas requeridas: {missing}")


def download_remote_csv(url: str, target: Path, max_bytes: int) -> tuple[str, int, str]:
    """Stream a remote CSV to *target*, returning checksum, size and final URL."""
    if max_bytes <= 0:
        raise RemoteCsvError("El límite de tamaño remoto debe ser mayor a cero")

    target.parent.mkdir(parents=True, exist_ok=True)
    direct_url = google_drive_download_url(url)
    digest = hashlib.sha256()
    size = 0
    preview = bytearray()
    try:
        with requests.get(
            direct_url,
            stream=True,
            timeout=(5, 120),
            headers={"User-Agent": "PirapireLocal/1.0", "Accept": "text/csv,*/*;q=0.8"},
        ) as response:
            response.raise_for_status()
            final_url = response.url
            with target.open("wb") as output:
                for chunk in response.iter_content(chunk_size=1024 * 1024):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > max_bytes:
                        raise RemoteCsvError(
                            f"El archivo remoto supera el límite de {max_bytes // 1024 // 1024} MB"
                        )
                    if len(preview) < 8192:
                        preview.extend(chunk[: 8192 - len(preview)])
                    digest.update(chunk)
                    output.write(chunk)
    except requests.RequestException as exc:
        raise RemoteCsvError(f"No se pudo descargar el CSV remoto: {exc}") from exc

    text = preview.decode("utf-8", errors="ignore").lower()
    if "quota exceeded" in text or "too many users have viewed or downloaded" in text:
        raise RemoteCsvError(
            "Google Drive bloqueó temporalmente la descarga por cuota excedida. "
            "Intente de nuevo cuando Drive la libere."
        )
    if "<html" in text or "<!doctype html" in text:
        raise RemoteCsvError("La URL remota devolvió una página web en lugar de un archivo CSV")
    if not size:
        raise RemoteCsvError("El archivo remoto está vacío")
    _validate_csv(target)
    return digest.hexdigest(), size, final_url


def import_remote_oracles_csv(session: Session, url: str, target: Path, max_bytes: int) -> dict:
    """Download a remote CSV, append unseen games, and rebuild derived series."""
    from .oracles_elixir_importer import _import_csv_file
    from ..series_builder import rebuild_series

    try:
        checksum, size, final_url = download_remote_csv(url, target, max_bytes)
        result = _import_csv_file(session, str(target), replace=True, prune_missing=False)
        rebuild_series(session)
        return {**result, "sha256": checksum, "file_size": size, "final_url": final_url}
    finally:
        target.unlink(missing_ok=True)
