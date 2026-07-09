"""Seed the database with a minimal analytical dataset."""

from sqlmodel import Session, select

from .database import engine, init_db
from .models import Match, Sport, Team


def seed() -> None:
    init_db()
    with Session(engine) as session:
        if session.exec(select(Sport)).first():
            print("Seed skipped: data already present.")
            return

        football = Sport(name="Football", slug="football")
        session.add(football)
        session.commit()
        session.refresh(football)

        team_a = Team(sport_id=football.id, name="Nacional", short_name="NAC")
        team_b = Team(sport_id=football.id, name="Penarol", short_name="PEN")
        session.add(team_a)
        session.add(team_b)
        session.commit()
        session.refresh(team_a)
        session.refresh(team_b)

        match = Match(
            sport_id=football.id,
            team_a_id=team_a.id,
            team_b_id=team_b.id,
            competition="Campeonato Uruguayo",
            status="scheduled",
        )
        session.add(match)
        session.commit()

        print("Seed completed.")


if __name__ == "__main__":
    seed()
