from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlmodel import Session, select
from ..database import get_session
from ..models_imports import ImportedOdds
from ..models_aposta import ApostaEvent
from ..utils.datetime_utils import event_time_display
from ..services.no_vig import calculate as calculate_no_vig

router = APIRouter(prefix="/api/events", tags=["events"])


def _event_for_key(session: Session, event_key: str) -> ApostaEvent:
    event = session.exec(select(ApostaEvent).where(ApostaEvent.event_key == event_key)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _legacy_key(session: Session, legacy_id: str) -> str:
    rows = session.exec(select(ImportedOdds).where(ImportedOdds.id == int(legacy_id))).all()
    keys = {row.event_key for row in rows if row.event_key}
    if not keys:
        raise HTTPException(status_code=404, detail="Legacy event id not found")
    if len(keys) != 1:
        raise HTTPException(status_code=409, detail="Legacy event id resolves ambiguously")
    return keys.pop()


@router.get("/{event_key}")
def event_detail(event_key: str, session: Session = Depends(get_session)):
    """Get all markets and odds for a specific event."""
    if event_key.isdigit():
        key = _legacy_key(session, event_key)
        return RedirectResponse(url=f"/api/events/{key}", status_code=308)
    canonical_event = _event_for_key(session, event_key)
    ref = session.exec(
        select(ImportedOdds).where(ImportedOdds.is_current, ImportedOdds.event_key == event_key).limit(1)
    ).first()
    if not ref:
        raise HTTPException(status_code=404, detail="Event has no active odds")

    # Find all odds for the same event identity
    odds = session.exec(
        select(ImportedOdds)
        .where(
            ImportedOdds.is_current,
            ImportedOdds.event_key == event_key,
        )
        .order_by(ImportedOdds.market_text, ImportedOdds.line)
    ).all()

    # Build event info
    first = ref
    event = {
        "event_key": event_key,
        "event_id": ref.id,
        "sport": first.sport,
        "team_a": first.team_a,
        "team_b": first.team_b,
        "competition": first.competition,
        "event_date": canonical_event.kickoff_utc or first.kickoff_utc or first.event_date_sort,
        "event_date_display": event_time_display(
            canonical_event.kickoff_utc or first.kickoff_utc or first.event_date_sort, first.event_time_status
        ),
        "event_time_status": first.event_time_status,
        "source": first.source_name,
        "total_odds": len(odds),
        "odds_count": len(odds),
        "market_count": len({o.market_key or o.source_market_id or o.canonical_market_id for o in odds}),
    }

    # Group markets
    markets = {}
    for o in odds:
        key = o.market_key or o.source_market_id or f"fallback:{o.canonical_market_id or o.market_text}|{o.line}|{o.period}|{o.player_name or ''}|{o.participant_name or ''}"
        if key not in markets:
            markets[key] = {
                "market_key": key,
                "market_text": o.raw_market_label or o.market_text,
                "raw_market_label": o.raw_market_label or o.market_text,
                "market_code": o.market_code,
                "line": o.line,
                "period": o.period,
                "map_number": o.map_number,
                "participant_name": o.participant_name,
                "player_name": o.player_name,
                "selections": [],
            }
        markets[key]["selections"].append(
            {
                "outcome_key": o.outcome_key or o.source_outcome_id,
                "selection": o.selection,
                "selection_raw": o.raw_outcome_label or o.selection or "",
                "odds_decimal": o.odds_decimal,
                "implied_probability": round(1.0 / o.odds_decimal, 4)
                if o.odds_decimal
                else 0,
            }
        )

    # No-vig is allowed only for explicitly identified, complete football markets.
    market_list = []
    for mk in markets.values():
        selections = mk["selections"]
        total_implied = sum(s["implied_probability"] for s in selections)
        probabilities, reason = calculate_no_vig(first.sport, mk.get("market_code"), selections)
        for selection, probability in zip(selections, probabilities):
            selection["no_vig_probability"] = probability
            selection["implied_pct"] = round(selection["implied_probability"] * 100, 1)
            selection["no_vig_pct"] = round(probability * 100, 1) if probability is not None else None
        available = reason is None
        mk["overround_pct"] = round((total_implied - 1.0) * 100, 2) if available else None
        mk["no_vig_available"] = available
        mk["no_vig_status"] = "available" if available else reason
        mk["selection_count"] = len(selections)
        mk["has_full_market"] = available
        market_list.append(mk)

    event["markets"] = market_list
    return event


@router.get("/{event_key}/statistics")
def event_statistics(
    event_key: str, session: Session = Depends(get_session), window: str = "365d"
):
    """Get descriptive statistics for a specific event."""
    if event_key.isdigit():
        key = _legacy_key(session, event_key)
        return RedirectResponse(url=f"/api/events/{key}/statistics", status_code=308)
    _event_for_key(session, event_key)
    ref = session.exec(select(ImportedOdds).where(ImportedOdds.event_key == event_key, ImportedOdds.is_current).limit(1)).first()
    if not ref:
        raise HTTPException(status_code=404, detail="Event not found")

    # Map Aposta Spanish names to football-data.org English names
    name_map = {
        "Espana": "Spain",
        "Belgica": "Belgium",
        "Noruega": "Norway",
        "Inglaterra": "England",
        "Argentina": "Argentina",
        "Suiza": "Switzerland",
        "Alemania": "Germany",
        "Francia": "France",
        "Italia": "Italy",
        "Brasil": "Brazil",
        "Portugal": "Portugal",
        "Uruguay": "Uruguay",
        "España": "Spain",
        "Bélgica": "Belgium",
    }

    stats = {
        "event_key": event_key,
        "event_id": ref.id,
        "team_a": ref.team_a,
        "team_b": ref.team_b,
        "sport": ref.sport,
        "window": window,
    }

    if ref.sport == "football":
        # Football: get team match history
        from ..models_football import FootballMatch, FootballTeam

        teams = session.exec(
            select(FootballTeam).where(
                FootballTeam.name.in_(
                    [
                        name_map.get(ref.team_a, ref.team_a),
                        name_map.get(ref.team_b, ref.team_b),
                    ]
                )
            )
        ).all()
        team_map = {t.name: t.id for t in teams}

        for team_name in [ref.team_a, ref.team_b]:
            tid = team_map.get(team_name)
            if not tid:
                stats[team_name] = {"matches": 0, "error": "team not found"}
                continue

            matches = session.exec(
                select(FootballMatch)
                .where(
                    (FootballMatch.home_team_id == tid)
                    | (FootballMatch.away_team_id == tid),
                    FootballMatch.home_score.is_not(None),
                )
                .order_by(FootballMatch.start_time.desc())
                .limit(50)
            ).all()

            wins = draws = losses = gf = ga = both_scored = over25 = 0
            recent_results = []
            for m in matches[:10]:
                is_home = m.home_team_id == tid
                scored = m.home_score if is_home else m.away_score
                conceded = m.away_score if is_home else m.home_score
                if scored > conceded:
                    wins += 1
                    result = "W"
                elif scored == conceded:
                    draws += 1
                    result = "D"
                else:
                    losses += 1
                    result = "L"
                gf += scored or 0
                ga += conceded or 0
                if (scored or 0) > 0 and (conceded or 0) > 0:
                    both_scored += 1
                if (scored or 0) + (conceded or 0) > 2.5:
                    over25 += 1
                recent_results.append(f"{result} {scored}-{conceded}")

            stats[team_name] = {
                "matches": len(matches),
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "goals_for": gf,
                "goals_against": ga,
                "avg_goals_for": round(gf / max(wins + draws + losses, 1), 1),
                "avg_goals_against": round(ga / max(wins + draws + losses, 1), 1),
                "both_scored": both_scored,
                "over_2_5": over25,
                "recent": recent_results,
            }

    elif ref.sport == "lol":
        # LoL: get team game stats from Leaguepedia
        from ..models_lol import LolTeamGameStat

        for team_name in [ref.team_a, ref.team_b]:
            games = session.exec(
                select(LolTeamGameStat)
                .where(
                    LolTeamGameStat.team_name == team_name,
                )
                .order_by(LolTeamGameStat.created_at.desc())
                .limit(30)
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
                "winrate": round(wins / max(len(games), 1) * 100, 1),
                "avg_kills": round(sum(kills) / max(len(kills), 1), 1)
                if kills
                else None,
                "avg_deaths": round(sum(deaths) / max(len(deaths), 1), 1)
                if deaths
                else None,
                "avg_towers": round(sum(towers) / max(len(towers), 1), 1)
                if towers
                else None,
            }

    return stats
