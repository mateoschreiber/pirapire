from sqlmodel import Session
from app.database import engine
from app.services.historical_ingestion import active_participants, run


def test_active_participants_are_scoped_to_current_odds():
    with Session(engine) as session:
        teams = active_participants(session)
        assert set(teams) == {"football", "lol"}


def test_unconfigured_api_football_does_not_break_ingestion():
    with Session(engine) as session:
        result = run(session)
        assert result["api_football"] in {"unconfigured", "db", "env"}
