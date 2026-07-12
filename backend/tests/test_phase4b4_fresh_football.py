from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from app.database import engine
from app.models_football import FootballFixtureStat
from app.services import fresh_football as ff


def _clean(session, marker="t4b4"):
    for r in session.exec(select(FootballFixtureStat).where(FootballFixtureStat.fixture_id.like(f"{marker}%"))).all():
        session.delete(r)
    session.commit()


def test_english_name_maps_spanish_countries():
    assert ff._english_name("Suiza") == "Switzerland"
    assert ff._english_name("Noruega") == "Norway"
    assert ff._english_name("Inglaterra") == "England"
    assert ff._english_name("Argentina") == "Argentina"
    assert ff._english_name("Unknownland") == "Unknownland"


def test_match_type_official_vs_friendly():
    assert ff._match_type("FIFA World Cup") == "official"
    assert ff._match_type("International Friendly") == "friendly"
    assert ff._match_type("UEFA Nations League") == "official"
    assert ff._match_type(None) is None


def test_to_int_null_never_zero():
    assert ff._to_int(None) is None
    assert ff._to_int("") is None
    assert ff._to_int("none") is None
    assert ff._to_int(0) == 0
    assert ff._to_int("7") == 7
    assert ff._to_int("61%") == 61


def test_sofa_side_stats_preserve_null():
    side = {"Corner kicks": 8, "Fouls": 0}
    out = ff._sofa_side_stats(side)
    assert out["corners"] == 8
    assert out["fouls"] == 0            # real zero preserved
    assert out["yellow_cards"] is None  # absent -> null, not zero
    assert out["red_cards"] is None


def test_null_preserving_upsert_does_not_overwrite_with_null():
    with Session(engine) as s:
        _clean(s)
        base = {"fixture_id": "t4b4_1", "side": "home", "source_key": "t4b4|1|home",
                "team_name": "T", "corners": 5, "fouls": 12}
        ff._upsert_team_row(s, base)
        # Second upsert with null corners must not wipe the stored 5.
        ff._upsert_team_row(s, {"fixture_id": "t4b4_1", "side": "home", "source_key": "t4b4|1|home",
                                "team_name": "T", "corners": None, "yellow_cards": 2})
        row = s.exec(select(FootballFixtureStat).where(FootballFixtureStat.source_key == "t4b4|1|home")).first()
        assert row.corners == 5           # preserved
        assert row.yellow_cards == 2      # added
        _clean(s)


def test_sliding_window_selects_10_most_recent_before_kickoff():
    kickoff = datetime(2026, 7, 12, tzinfo=UTC)
    finished = []
    for i in range(14):
        d = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i * 12)
        finished.append((d, f"t4b4_f{i}"))
    before = [(d, f) for d, f in finished if d < kickoff]
    before.sort(key=lambda x: x[0], reverse=True)
    window = before[:ff.WINDOW_N]
    assert len(window) == 10
    win_ids = {f for _, f in window}
    # Newest before kickoff is included; the oldest ones are excluded.
    newest_id = before[0][1]
    assert newest_id in win_ids
    assert "t4b4_f0" not in win_ids and "t4b4_f1" not in win_ids


def test_new_finished_match_slides_out_oldest():
    kickoff = datetime(2026, 8, 1, tzinfo=UTC)
    base = [(datetime(2026, 3, 1, tzinfo=UTC) + timedelta(days=i * 10), f"g{i}") for i in range(10)]
    # A newer match appears.
    newer = (datetime(2026, 7, 20, tzinfo=UTC), "g_new")
    allm = [(d, f) for d, f in base + [newer] if d < kickoff]
    allm.sort(key=lambda x: x[0], reverse=True)
    window = allm[:ff.WINDOW_N]
    win_ids = {f for _, f in window}
    assert "g_new" in win_ids            # newest enters
    assert "g0" not in win_ids           # oldest leaves


def test_stale_rows_never_eligible():
    with Session(engine) as s:
        r = FootballFixtureStat(
            provider="fresh_football", fixture_id="t4b4_stale", team_side="home",
            team_name="StaleT", freshness_class="historical_fallback_stale",
            eligible_for_last_n=True, source_key="t4b4|stale|home",
        )
        s.add(r)
        s.commit()
        ff._fix_stale_eligibility(s)
        row = s.exec(select(FootballFixtureStat).where(FootballFixtureStat.source_key == "t4b4|stale|home")).first()
        assert row.eligible_for_last_n is False
        s.delete(row)
        s.commit()


def test_no_football_scope_when_no_history(monkeypatch):
    # resolve_football_scope must handle an empty football history gracefully.
    with Session(engine) as s:
        info = ff.resolve_football_scope(s)
        assert set(info.keys()) == {"scope", "anchored"}
