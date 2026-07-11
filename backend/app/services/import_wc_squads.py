"""Import World Cup squads into FootballPlayer table."""

import json
import sys
import urllib.request

from sqlmodel import Session, select

sys.path.insert(0, "/app")

from app.config import settings
from app.database import engine, init_db
from app.models_football import FootballPlayer, FootballTeam
from app.services.secret_provider import SecretProvider


def import_wc_squads():
    api_key, source = SecretProvider.get_secret(
        "football_data_org", "api_key", mark_used=True
    )
    if settings.football_sync_ui_bootstrap_required and source != "ui":
        raise RuntimeError("football_sync_blocked_pending_ui_credential")
    if not api_key:
        raise RuntimeError("football_data_api_key_not_configured")

    url = "https://api.football-data.org/v4/competitions/WC/teams"
    req = urllib.request.Request(
        url,
        headers={"X-Auth-Token": api_key},
    )
    data = json.loads(urllib.request.urlopen(req, timeout=20).read())

    with Session(engine) as session:
        teams = session.exec(select(FootballTeam)).all()
        team_by_name = {team.name.lower(): team for team in teams if team.name}
        team_by_short = {
            team.short_name.lower(): team for team in teams if team.short_name
        }

        inserted = 0
        skipped = 0
        for team_data in data.get("teams", []):
            name = team_data.get("name", "")
            football_team = team_by_name.get(name.lower()) or team_by_short.get(
                name.lower()
            )
            if not football_team:
                print(f"  No match: {name}")
                continue

            for player in team_data.get("squad", []):
                player_name = player.get("name", "")
                source_key = f"football-data|WC|{football_team.id}|{player_name}"
                existing = session.exec(
                    select(FootballPlayer).where(
                        FootballPlayer.source_key == source_key
                    )
                ).first()
                if existing:
                    skipped += 1
                    continue

                session.add(
                    FootballPlayer(
                        source_name="football-data",
                        source_id=str(football_team.id),
                        name=player_name,
                        position=player.get("position", ""),
                        shirt_number=player.get("shirtNumber"),
                        date_of_birth=player.get("dateOfBirth", ""),
                        nationality=player.get("nationality", ""),
                        team_id=football_team.id,
                        team_name=name,
                        source_key=source_key,
                    )
                )
                inserted += 1

            session.commit()

        print(f"Inserted: {inserted}, Skipped: {skipped}")
        return inserted


if __name__ == "__main__":
    init_db()
    import_wc_squads()
