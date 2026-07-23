from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.database import engine
from app.models_lol import LolMatchEvent, LolMatchStatisticsReadModel
from app.services import lol_metrics_engine


def _scheduled_match(key: str) -> LolMatchEvent:
    return LolMatchEvent(
        match_key=key,
        source_name="test",
        source_match_id=key,
        league="LCK",
        team_a="Alpha",
        team_b="Beta",
        start_time_utc=datetime.now(timezone.utc) + timedelta(days=1),
        status="scheduled",
    )


def test_precompute_persists_and_reuses_statistics(monkeypatch):
    with Session(engine) as session:
        match = _scheduled_match("cache-precompute-match")
        session.add(match)
        session.commit()

        calls = []

        def computed(_, match_key):
            calls.append(match_key)
            return ({"estimated_market": {"available": True}}, {"team_a": "complete"})

        monkeypatch.setattr(lol_metrics_engine, "compute_match_statistics", computed)
        first = lol_metrics_engine.precompute_upcoming_stats(session)
        second = lol_metrics_engine.precompute_upcoming_stats(session)

        cached = session.exec(
            select(LolMatchStatisticsReadModel).where(
                LolMatchStatisticsReadModel.match_key == match.match_key
            )
        ).one()
        assert first["precomputed"] >= 1
        assert second["skipped"] >= 1
        assert calls.count(match.match_key) == 1
        assert cached.status == "ready"
        assert cached.payload_json["estimated_market"]["available"] is True


def test_statistics_endpoint_serves_cache_without_recomputing():
    from fastapi.testclient import TestClient
    from app.main import app

    with Session(engine) as session:
        match = _scheduled_match("cache-api-match")
        session.add(match)
        session.commit()
        lol_metrics_engine.store_match_statistics(
            session,
            match,
            {"estimated_market": {"available": False, "reason": "test"}},
            {"team_a": "unavailable", "team_b": "unavailable"},
        )
        session.commit()

    response = TestClient(app).get("/api/lol/matches/cache-api-match/statistics")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"
    assert response.json()["payload"]["estimated_market"]["reason"] == "test"
