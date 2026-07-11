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
        conn.commit()
    finally:
        conn.close()
