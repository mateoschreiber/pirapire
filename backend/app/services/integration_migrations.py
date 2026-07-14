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
        _quality = {
            "source": "TEXT",
            "source_url": "TEXT",
            "source_id": "TEXT",
            "observed_at": "TIMESTAMP",
            "data_as_of": "TIMESTAMP",
            "freshness_class": "TEXT",
            "eligible_for_last_n": "INTEGER DEFAULT 0",
        }
        _add_columns(conn, "footballfixturestat", _quality)
        _add_columns(conn, "footballfixturestat", {"candidate_last_n": "INTEGER DEFAULT 0"})
        _add_columns(conn, "footballfixturestat", {"penalties_awarded": "INTEGER", "match_type": "TEXT"})
        _add_columns(
            conn,
            "footballfixtureplayerstat",
            {
                "source": "TEXT",
                "source_id": "TEXT",
                "observed_at": "TIMESTAMP",
                "freshness_class": "TEXT",
                "eligible_for_last_n": "INTEGER DEFAULT 0",
            },
        )
        _add_columns(conn, "lolseries", {**_quality, "game_ids_json": "TEXT", "series_status": "TEXT"})
        # Phase 4D1: event lifecycle + refresh queue.
        _add_columns(conn, "apostaevent", {"local_event_state": "TEXT", "last_reconciled_at": "TIMESTAMP"})
        _create_indexes(conn)
        conn.commit()
    finally:
        conn.close()


def _create_indexes(conn) -> None:
    """Composite indexes justified by EXPLAIN QUERY PLAN for Phase 4C read paths."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    idx = [
        ("ix_ethw_event_team_rank", "eventteamhistorywindow", "event_key, team, rank"),
        ("ix_lgh_source_match", "lolgamehistory", "source_name, match_id"),
        ("ix_ltgs_source_game", "lolteamgamestat", "source_name, source_game_id"),
        ("ix_lpgs_source_game", "lolplayergamestat", "source_name, source_game_id"),
        ("ix_esrm_event_sport", "eventstatisticsreadmodel", "event_key, sport"),
        ("ix_lolseries_status", "lolseries", "series_status"),
        ("ix_ffs_provider_source", "footballfixturestat", "provider, source_id"),
    ]
    for name, table, cols in idx:
        if table in tables:
            conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {table} ({cols})")


def _add_columns(conn, table: str, additions: dict[str, str]) -> None:
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if not existing:
        return
    for name, definition in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")