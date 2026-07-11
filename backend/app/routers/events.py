
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func
from ..database import get_session
from ..models_imports import ImportedOdds

router = APIRouter(prefix="/api/events", tags=["events"])

@router.get("/{event_id}")
def event_detail(event_id: int, session: Session = Depends(get_session)):
    """Get all markets and odds for a specific event."""
    # Find the reference event row
    ref = session.exec(
        select(ImportedOdds).where(
            ImportedOdds.is_current == True,
            ImportedOdds.id == event_id,
        ).limit(1)
    ).first()

    if not ref:
        raise HTTPException(status_code=404, detail="Event not found")

    # Find all odds for the same event identity
    odds = session.exec(
        select(ImportedOdds).where(
            ImportedOdds.is_current == True,
            ImportedOdds.sport == ref.sport,
            ImportedOdds.team_a == ref.team_a,
            ImportedOdds.team_b == ref.team_b,
            ImportedOdds.competition == ref.competition,
        ).order_by(ImportedOdds.market_text, ImportedOdds.line)
    ).all()

    # Build event info
    first = ref
    event = {
        "event_id": event_id,
        "sport": first.sport,
        "team_a": first.team_a,
        "team_b": first.team_b,
        "competition": first.competition,
        "event_date": first.event_date_sort,
        "source": first.source_name,
        "total_odds": len(odds),
    }
    
    # Group markets
    markets = {}
    for o in odds:
        key = f"{o.market_text}|{o.line}|{o.market_code}"
        if key not in markets:
            markets[key] = {
                "market_text": o.market_text,
                "market_code": o.market_code,
                "line": o.line,
                "selections": []
            }
        markets[key]["selections"].append({
            "selection": o.selection,
            "selection_raw": (o.selection or ""),
            "odds_decimal": o.odds_decimal,
            "implied_probability": round(1.0 / o.odds_decimal, 4) if o.odds_decimal else 0,
        })
    
    # Calculate no-vig and probability for each market
    market_list = []
    for mk in markets.values():
        selections = mk["selections"]
        # Calculate overround
        total_implied = sum(s["implied_probability"] for s in selections)
        overround = round((total_implied - 1.0) * 100, 2) if selections else 0
        
        # Calculate no-vig probabilities
        for s in selections:
            s["no_vig_probability"] = round(s["implied_probability"] / total_implied, 4) if total_implied > 0 else None
            s["implied_pct"] = round(s["implied_probability"] * 100, 1)
            s["no_vig_pct"] = round((s["no_vig_probability"] or 0) * 100, 1)
        
        mk["overround_pct"] = overround
        mk["selection_count"] = len(selections)
        mk["has_full_market"] = len(selections) >= 2  # Simplified check
        market_list.append(mk)
    
    event["markets"] = market_list
    return event


@router.get("/{event_id}/statistics")
def event_statistics(event_id: int, session: Session = Depends(get_session), window: str = "365d"):
    """Get descriptive statistics for a specific event."""
    ref = session.get(ImportedOdds, event_id)
    if not ref or not ref.is_current:
        raise HTTPException(status_code=404, detail="Event not found")
    
    
    # Map Aposta Spanish names to football-data.org English names
    name_map = {"Espana": "Spain", "Belgica": "Belgium", "Noruega": "Norway",
                "Inglaterra": "England", "Argentina": "Argentina", "Suiza": "Switzerland",
                "Alemania": "Germany", "Francia": "France", "Italia": "Italy",
                "Brasil": "Brazil", "Portugal": "Portugal", "Uruguay": "Uruguay",
                "España": "Spain", "Bélgica": "Belgium"}

    stats = {"event_id": event_id, "team_a": ref.team_a, "team_b": ref.team_b, "sport": ref.sport, "window": window}
    
    if ref.sport == "football":
        # Football: get team match history
        from ..models_football import FootballMatch, FootballTeam
        teams = session.exec(select(FootballTeam).where(FootballTeam.name.in_([name_map.get(ref.team_a, ref.team_a), name_map.get(ref.team_b, ref.team_b)]))).all()
        team_map = {t.name: t.id for t in teams}
        
        for team_name in [ref.team_a, ref.team_b]:
            tid = team_map.get(team_name)
            if not tid:
                stats[team_name] = {"matches": 0, "error": "team not found"}
                continue
            
            matches = session.exec(
                select(FootballMatch).where(
                    (FootballMatch.home_team_id == tid) | (FootballMatch.away_team_id == tid),
                    FootballMatch.home_score.is_not(None),
                ).order_by(FootballMatch.start_time.desc()).limit(50)
            ).all()
            
            wins = draws = losses = gf = ga = both_scored = over25 = 0
            recent_results = []
            for m in matches[:10]:
                is_home = m.home_team_id == tid
                scored = m.home_score if is_home else m.away_score
                conceded = m.away_score if is_home else m.home_score
                if scored > conceded: wins += 1; result = "W"
                elif scored == conceded: draws += 1; result = "D"
                else: losses += 1; result = "L"
                gf += scored or 0
                ga += conceded or 0
                if (scored or 0) > 0 and (conceded or 0) > 0: both_scored += 1
                if (scored or 0) + (conceded or 0) > 2.5: over25 += 1
                recent_results.append(f"{result} {scored}-{conceded}")
            
            stats[team_name] = {
                "matches": len(matches),
                "wins": wins, "draws": draws, "losses": losses,
                "goals_for": gf, "goals_against": ga,
                "avg_goals_for": round(gf/max(wins+draws+losses,1), 1),
                "avg_goals_against": round(ga/max(wins+draws+losses,1), 1),
                "both_scored": both_scored,
                "over_2_5": over25,
                "recent": recent_results,
            }
    
    elif ref.sport == "lol":
        # LoL: get team game stats from Leaguepedia
        from ..models_lol import LolTeamGameStat
        for team_name in [ref.team_a, ref.team_b]:
            games = session.exec(
                select(LolTeamGameStat).where(
                    LolTeamGameStat.team_name == team_name,
                ).order_by(LolTeamGameStat.created_at.desc()).limit(30)
            ).all()
            
            if not games:
                stats[team_name] = {"matches": 0, "note": "no data"}
                continue
            
            wins = sum(1 for g in games if g.result == 1)
            kills = [g.kills for g in games if g.kills]
            deaths = [g.deaths for g in games if g.deaths]
            towers = [g.towers for g in games if g.towers]
            
            stats[team_name] = {
                "matches": len(games),
                "wins": wins,
                "losses": len(games) - wins,
                "winrate": round(wins/max(len(games),1)*100, 1),
                "avg_kills": round(sum(kills)/max(len(kills),1), 1) if kills else None,
                "avg_deaths": round(sum(deaths)/max(len(deaths),1), 1) if deaths else None,
                "avg_towers": round(sum(towers)/max(len(towers),1), 1) if towers else None,
            }
    
    return stats


    return event
    event["market_count"] = len(market_list)
    
