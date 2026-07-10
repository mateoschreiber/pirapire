
"""Import World Cup squads into FootballPlayer table."""
import json, urllib.request, sys
sys.path.insert(0, '/app')
from datetime import datetime, timezone
from sqlmodel import Session, select
from app.database import engine, init_db
from app.models_football import FootballPlayer, FootballTeam

API_KEY = 'd3ade4a1ca88431fae57508399ed1b7f'

def import_wc_squads():
    url = 'https://api.football-data.org/v4/competitions/WC/teams'
    req = urllib.request.Request(url, headers={'X-Auth-Token': API_KEY})
    data = json.loads(urllib.request.urlopen(req, timeout=20).read())
    
    with Session(engine) as session:
        teams = session.exec(select(FootballTeam)).all()
        team_by_name = {}
        team_by_short = {}
        for t in teams:
            if t.name:
                team_by_name[t.name.lower()] = t
            if t.short_name:
                team_by_short[t.short_name.lower()] = t
        
        inserted = 0
        skipped = 0
        
        for team_data in data.get('teams', []):
            name = team_data.get('name', '')
            ft = team_by_name.get(name.lower()) or team_by_short.get(name.lower())
            if not ft:
                print(f'  No match: {name}')
                continue
            
            squad = team_data.get('squad', [])
            for p in squad:
                pname = p.get('name', '')
                source_key = f'football-data|WC|{ft.id}|{pname}'
                
                existing = session.exec(
                    select(FootballPlayer).where(FootballPlayer.source_key == source_key)
                ).first()
                if existing:
                    skipped += 1
                    continue
                
                session.add(FootballPlayer(
                    source_name='football-data',
                    source_id=str(ft.id),
                    name=pname,
                    position=p.get('position', ''),
                    shirt_number=p.get('shirtNumber'),
                    date_of_birth=p.get('dateOfBirth', ''),
                    nationality=p.get('nationality', ''),
                    team_id=ft.id,
                    team_name=name,
                    source_key=source_key,
                ))
                inserted += 1
            
            session.commit()
        
        print(f'Inserted: {inserted}, Skipped: {skipped}')
        return inserted

if __name__ == '__main__':
    init_db()
    import_wc_squads()
