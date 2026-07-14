from datetime import UTC, datetime, timedelta
from typing import Optional

from sqlmodel import Session, func, select

from ..config import settings
from ..models_aposta import ApostaSyncRun
from ..models_football import FootballCompetition, FootballMatch
from ..models_imports import ImportedOdds, ManualImportBatch
from ..models_lol import LolChampion, LolGameHistory, LolPatch, LolPlayerGameStat, LolTeamGameStat
from ..models_recommendations import BetRecommendation, ComboRecommendation, RecommendationRun


def now() -> datetime:
    return datetime.now(UTC)


def _safe_count(session: Session, model) -> int:
    try:
        return session.exec(select(func.count()).select_from(model)).one()
    except Exception:
        return 0


def _safe_first(session: Session, model, order_by_col):
    try:
        return session.exec(select(model).order_by(order_by_col.desc())).first()
    except Exception:
        return None


def get_football_state(session: Session) -> dict:
    try:
        competitions = _safe_count(session, FootballCompetition)
        future_matches = session.exec(
            select(func.count()).select_from(FootballMatch)
            .where(FootballMatch.start_time > now())
        ).one()
        finished_matches = session.exec(
            select(func.count()).select_from(FootballMatch)
            .where(FootballMatch.status == 'FINISHED')
        ).one()
        total_matches = _safe_count(session, FootballMatch)

        stale_threshold = now() - timedelta(hours=settings.source_stale_hours)
        recent_ok = session.exec(
            select(FootballMatch)
            .where(FootballMatch.retrieved_at >= stale_threshold)
            .order_by(FootballMatch.retrieved_at.desc())
        ).first()
        last_sync = None
        if recent_ok is not None:
            last_sync = recent_ok.retrieved_at.isoformat() if recent_ok.retrieved_at else None

        return {
            "last_sync": last_sync,
            "stale": last_sync is None,
            "competitions": competitions,
            "future_matches": future_matches,
            "finished_matches": finished_matches,
            "total_matches": total_matches,
        }
    except Exception as e:
        return {
            "last_sync": None,
            "stale": True,
            "competitions": 0,
            "future_matches": 0,
            "finished_matches": 0,
            "total_matches": 0,
            "warning": str(e),
        }


def get_lol_state(session: Session) -> dict:
    try:
        last_patch = _safe_first(session, LolPatch, LolPatch.retrieved_at)
        last_static_sync = last_patch.retrieved_at.isoformat() if last_patch and last_patch.retrieved_at else None

        champions = _safe_count(session, LolChampion)
        patches = _safe_count(session, LolPatch)
        games = _safe_count(session, LolGameHistory)

        teams = session.exec(
            select(func.count(func.distinct(LolTeamGameStat.team_name)))
            .where(LolTeamGameStat.team_name.isnot(None))
        ).one() or 0

        players = session.exec(
            select(func.count(func.distinct(LolPlayerGameStat.player_name)))
            .where(LolPlayerGameStat.player_name.isnot(None))
        ).one() or 0

        last_history_import = _safe_first(session, LolGameHistory, LolGameHistory.created_at)
        history_last_import = last_history_import.created_at.isoformat() if last_history_import and last_history_import.created_at else None

        return {
            "last_static_sync": last_static_sync,
            "history_last_import": history_last_import,
            "champions": champions,
            "patches": patches,
            "games": games,
            "teams": teams,
            "players": players,
            "player_data_available": players > 0,
        }
    except Exception as e:
        return {
            "last_static_sync": None,
            "history_last_import": None,
            "champions": 0,
            "patches": 0,
            "games": 0,
            "teams": 0,
            "players": 0,
            "player_data_available": False,
            "warning": str(e),
        }


def get_aposta_state(session: Session) -> dict:
    """Dashboard summary using SQL aggregates, never the complete odds history."""
    try:
        mode = settings.aposta_sync_mode or "disabled"
        last_sync_run = _safe_first(session, ApostaSyncRun, ApostaSyncRun.id)
        now_naive = datetime.now(UTC).replace(tzinfo=None)
        source_filter = ImportedOdds.source_name == "aposta_la"

        historical_odds = session.exec(
            select(func.count()).select_from(ImportedOdds).where(source_filter)
        ).one()
        current_odds = session.exec(
            select(func.count()).select_from(ImportedOdds).where(
                source_filter, ImportedOdds.is_current, ImportedOdds.event_date > now_naive
            )
        ).one()
        expired_odds = session.exec(
            select(func.count()).select_from(ImportedOdds).where(
                source_filter,
                ImportedOdds.is_current,
                ImportedOdds.event_date.is_not(None),
                ImportedOdds.event_date <= now_naive,
            )
        ).one()
        unmatched_odds = session.exec(
            select(func.count()).select_from(ImportedOdds).where(
                source_filter,
                ImportedOdds.market_code.is_(None),
                ImportedOdds.market_id.is_(None),
            )
        ).one()
        unmapped_markets = session.exec(
            select(ImportedOdds.sport, ImportedOdds.market_text)
            .where(
                source_filter,
                ImportedOdds.market_code.is_(None),
                ImportedOdds.market_id.is_(None),
            )
            .distinct()
        ).all()

        return {
            "mode": mode,
            "last_snapshot": last_sync_run.finished_at.isoformat()
            if last_sync_run and last_sync_run.finished_at
            else None,
            "last_run_status": last_sync_run.status if last_sync_run else None,
            "historical_odds": historical_odds,
            "current_odds": current_odds,
            "expired_odds": expired_odds,
            "unmatched_odds": unmatched_odds,
            "unmapped_markets": len(unmapped_markets),
        }
    except Exception as e:
        return {
            "mode": "unknown",
            "last_snapshot": None,
            "last_run_status": None,
            "historical_odds": 0,
            "current_odds": 0,
            "expired_odds": 0,
            "unmatched_odds": 0,
            "unmapped_markets": 0,
            "warning": str(e),
        }


def get_recommendations_state(session: Session) -> dict:
    try:
        last_run = _safe_first(session, RecommendationRun, RecommendationRun.id)
        latest_run = last_run.finished_at.isoformat() if last_run and last_run.finished_at else None

        singles = 0
        combos = 0
        if last_run:
            singles = session.exec(
                select(func.count()).select_from(BetRecommendation)
                .where(BetRecommendation.run_id == last_run.id)
            ).one()
            combos = session.exec(
                select(func.count()).select_from(ComboRecommendation)
                .where(ComboRecommendation.run_id == last_run.id)
            ).one()

        blockers = []
        if latest_run is None:
            blockers.append("No se ha ejecutado ningun run de recomendacion")

        aposta_state = get_aposta_state(session)
        if aposta_state["current_odds"] == 0:
            blockers.append("No hay cuotas actuales vigentes")
        if aposta_state["historical_odds"] > 0 and aposta_state["current_odds"] == 0:
            blockers.append("Todas las cuotas importadas estan vencidas; importar CSV mas reciente")

        if singles == 0 and last_run:
            if aposta_state["current_odds"] == 0:
                blockers.append("No hay cuotas actuales para recomendar")
            if aposta_state["unmapped_markets"] > 0:
                blockers.append("Hay mercados no mapeados; revisar /aposta/unmapped-markets")

        football_state = get_football_state(session)
        if football_state["stale"] and football_state["competitions"] == 0:
            blockers.append("Datos de futbol no sincronizados")
        if football_state["future_matches"] == 0 and football_state["competitions"] > 0:
            blockers.append("No hay partidos de futbol futuros")

        lol_state = get_lol_state(session)
        if lol_state["games"] == 0:
            blockers.append("No hay datos historicos de LoL")

        return {
            "latest_run": latest_run,
            "last_run_id": last_run.id if last_run else None,
            "singles": singles,
            "combos": combos,
            "blockers": blockers if blockers else [],
        }
    except Exception as e:
        return {
            "latest_run": None,
            "last_run_id": None,
            "singles": 0,
            "combos": 0,
            "blockers": [str(e)],
        }


def get_full_state(session: Session) -> dict:
    football = get_football_state(session)
    lol = get_lol_state(session)
    aposta = get_aposta_state(session)
    recommendations = get_recommendations_state(session)
    recommendations["football"] = football
    recommendations["lol"] = lol
    recommendations["aposta"] = aposta

    has_blockers = len(recommendations.get("blockers", [])) > 0

    return {
        "health": "ok",
        "football": football,
        "lol": lol,
        "aposta": aposta,
        "recommendations": recommendations,
        "has_blockers": has_blockers,
    }
