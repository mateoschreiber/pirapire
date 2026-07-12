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
        # In tests live ingestion is disabled; the coordinator must degrade
        # gracefully without raising and without hitting the network.
        assert result["api_football"] in {"unconfigured", "db", "env", "ui", "disabled", "skipped_active_run"}
        assert "at" in result
