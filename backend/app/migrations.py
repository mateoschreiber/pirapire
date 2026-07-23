from sqlalchemy import inspect, text
from sqlmodel import Session


def _columns(session: Session, table: str) -> set[str]:
    return {row[1] for row in session.exec(text(f"PRAGMA table_info({table})")).all()}


def _add(session: Session, table: str, definition: str) -> None:
    name = definition.split()[0]
    if name not in _columns(session, table):
        session.exec(text(f"ALTER TABLE {table} ADD COLUMN {definition}"))


def _rename_incompatible_legacy_table(
    session: Session,
    table: str,
    required_columns: set[str],
    legacy_table: str,
) -> bool:
    """Preserve a pre-LoL table that reuses a current table name.

    Earlier versions used ``datasource`` and ``sourcerun`` for a different
    domain model.  SQLite's ``CREATE TABLE IF NOT EXISTS`` leaves those tables
    in place, which makes the current source configuration endpoints fail at
    runtime.  Rename the incompatible table rather than dropping operational
    history; the current table is created immediately afterwards.
    """
    tables = set(inspect(session.bind).get_table_names())
    if table not in tables or required_columns.issubset(_columns(session, table)):
        return False
    if legacy_table in tables:
        raise RuntimeError(
            f"Cannot migrate {table}: incompatible table preserved as {legacy_table} already exists"
        )
    session.exec(text(f'ALTER TABLE "{table}" RENAME TO "{legacy_table}"'))
    return True


def upgrade(engine) -> None:
    """Idempotent SQLite schema upgrades for installations predating Alembic."""
    from .models_lol import DataSource, SourceRun

    recreate_sources = False
    recreate_source_runs = False
    with Session(engine) as session:
        recreate_sources = _rename_incompatible_legacy_table(
            session,
            "datasource",
            {"code", "display_name", "config_json"},
            "legacy_datasource",
        )
        recreate_source_runs = _rename_incompatible_legacy_table(
            session,
            "sourcerun",
            {"source_code", "job", "details_json"},
            "legacy_sourcerun",
        )
        session.commit()

        # ``create_all`` ran before this migration, while the incompatible
        # tables still occupied these names.  Create only the two replacement
        # tables after their legacy counterparts have been retained.
        if recreate_sources:
            DataSource.__table__.create(engine, checkfirst=True)
        if recreate_source_runs:
            SourceRun.__table__.create(engine, checkfirst=True)

        for definition in ("series_id INTEGER REFERENCES lolseries(id)",):
            _add(session, "lolgamehistory", definition)
        for definition in (
            "team_id INTEGER REFERENCES lolteam(id)",
            "opponent_team_id INTEGER REFERENCES lolteam(id)",
            "final_gold INTEGER",
            "earned_gold INTEGER",
        ):
            _add(session, "lolteamgamestat", definition)
        for definition in (
            "team_id INTEGER REFERENCES lolteam(id)",
            "player_id INTEGER REFERENCES lolplayer(id)",
            "final_gold INTEGER",
        ):
            _add(session, "lolplayergamestat", definition)
        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_lolmatchevent_status_start ON lolmatchevent(status, start_time_utc)",
            "CREATE INDEX IF NOT EXISTS ix_lolseries_team_a_stats ON lolseries(team_a, source_name, complete, last_game_at DESC)",
            "CREATE INDEX IF NOT EXISTS ix_lolseries_team_b_stats ON lolseries(team_b, source_name, complete, last_game_at DESC)",
        ):
            session.exec(text(statement))
        session.commit()
