"""Small idempotent SQLite migrations for integration metadata."""

import sqlite3

from ..config import settings


def run_migrations() -> None:
    if not settings.database_url.startswith("sqlite:///"):
        return
    conn = sqlite3.connect(settings.database_url.replace("sqlite:///", ""))
    try:
        columns = {
            row[1]
            for row in conn.execute("PRAGMA table_info(integrationcredential)").fetchall()
        }
        additions = {
            "accepted_risk_at": "TIMESTAMP",
            "accepted_by": "TEXT",
            "accepted_reason": "TEXT",
            "key_type": "TEXT",
            "default_platform": "TEXT",
            "regional_routes": "TEXT",
            "expires_at": "TIMESTAMP",
        }
        for name, definition in additions.items():
            if name not in columns:
                conn.execute(
                    f"ALTER TABLE integrationcredential ADD COLUMN {name} {definition}"
                )
        _add_columns(
            conn,
            "integrationproviderstate",
            {"next_retry_at": "TIMESTAMP", "cursor_json": "TEXT"},
        )
        _add_columns(
            conn,
            "lolgamehistory",
            {"match_id": "TEXT", "n_game_in_match": "INTEGER"},
        )
        conn.commit()
    finally:
        conn.close()


def _add_columns(conn, table: str, additions: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if not existing:
        return
    for name, definition in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")
