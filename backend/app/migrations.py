from sqlalchemy import text
from sqlmodel import Session


def _columns(session: Session, table: str) -> set[str]:
    return {row[1] for row in session.exec(text(f"PRAGMA table_info({table})")).all()}


def _add(session: Session, table: str, definition: str) -> None:
    name = definition.split()[0]
    if name not in _columns(session, table):
        session.exec(text(f"ALTER TABLE {table} ADD COLUMN {definition}"))


def upgrade(engine) -> None:
    """Idempotent SQLite schema upgrades for installations predating Alembic."""
    with Session(engine) as session:
        for definition in (
            "series_id INTEGER REFERENCES lolseries(id)",
        ):
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
        session.commit()