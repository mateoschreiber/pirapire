from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_dashboard_html():
    response = client.get("/")
    assert response.status_code == 200
    assert "Próximos encuentros" in response.text
    assert 'data-testid="live-clock"' in response.text


def test_sources_html_has_upload_flow():
    response = client.get("/sources")
    assert response.status_code == 200
    assert 'id="preview-button"' in response.text
    assert 'id="save-button"' in response.text
    assert "100 * 1024 * 1024" in response.text
    assert 'id="sync-all-button"' in response.text
    assert 'name="replace_existing"' in response.text
    assert 'id="source-config-form"' in response.text
    assert 'id="custom-source-form"' in response.text
    assert 'id="upload-progress-bar"' in response.text
    assert "XMLHttpRequest" in response.text
    assert "process_queued_oracle_uploads" not in response.text


def test_match_detail_html():
    response = client.get("/lol/matches/test123")
    assert response.status_code == 200
    assert "Cargando" in response.text
    assert 'data-testid="live-clock"' in response.text
    assert 'id="market-source-badge"' in response.text
    assert "Cuotas calculadas del enfrentamiento" in response.text


def test_upcoming_api():
    response = client.get("/api/lol/matches/upcoming?hours=48")
    assert response.status_code == 200
    assert response.json()["window_hours"] == 48


def test_upcoming_timezone():
    assert client.get("/api/lol/matches/upcoming").json()["timezone"] == "America/Asuncion"


def test_api_serializes_naive_sqlite_match_times_as_utc():
    from datetime import datetime
    from app.routers.lol_api import _utc_iso

    assert _utc_iso(datetime(2026, 7, 16, 9, 0)) == "2026-07-16T09:00:00+00:00"


def test_match_not_found():
    assert client.get("/api/lol/matches/nonexistent_key_xyz").status_code == 404


def test_static_assets():
    css = client.get("/static/css/styles.css")
    assert css.status_code == 200
    assert 'font-family: "Inter"' in css.text
    assert client.get("/static/fonts/inter-latin.woff2").status_code == 200
    js = client.get("/static/js/app.js")
    assert js.status_code == 200
    assert 'el("live-clock")' in js.text
    assert "el(live-clock)" not in js.text

def test_competition_classifier_excludes_academies():
    from app.routers.lol_api import _competition_code
    assert _competition_code("LCK/2026 Season/Rounds 3-4") == "LCK"
    assert _competition_code("LCK CL/2026 Season/Rounds 3-4") is None
    assert _competition_code("LCS/2026 Season") == "LCS"
    assert _competition_code("CBLOL/2026 Season") == "CBLOL"
    assert _competition_code("LTA North/2025 Season") == "LCS"
    assert _competition_code("LTA South/2025 Season") == "CBLOL"
    assert _competition_code("LTA/2025 Season") is None
    assert _competition_code("2026 Mid-Season Invitational") == "MSI"
    assert _competition_code("Esports World Cup 2026") == "EWC"
    assert _competition_code("World Championship/2026") == "WORLDS"


def test_upcoming_api_exposes_only_allowed_competitions():
    payload = client.get("/api/lol/matches/upcoming?hours=336").json()
    assert payload["allowed_competitions"] == [
        "LCK", "LPL", "LEC", "LCS", "CBLOL", "LCP",
        "WORLDS", "MSI", "FIRST STAND", "EWC",
    ]
    assert len(payload["competitions"]) == 10
    allowed = {"LCK", "LPL", "LEC", "LCS", "CBLOL", "LCP", "WORLDS", "MSI", "FIRST_STAND", "EWC"}
    assert all(match["competition_code"] in allowed for match in payload["matches"])


def test_2026_official_competition_rosters_are_complete():
    payload = client.get("/api/lol/matches/upcoming?hours=336").json()
    by_code = {item["code"]: item for item in payload["competitions"]}
    expected_counts = {"LCK": 10, "LPL": 14, "LEC": 10, "LCS": 8, "CBLOL": 8, "LCP": 8, "MSI": 11, "FIRST_STAND": 8, "EWC": 16}
    assert {code: by_code[code]["team_count"] for code in expected_counts} == expected_counts
    assert set(by_code["LCK"]["qualified_teams"]) == {
        "Gen.G Esports", "T1", "NONGSHIM RED FORCE", "DN SOOPers", "HANJIN BRION",
        "Hanwha Life Esports", "Dplus KIA", "kt Rolster", "BNK FEARX", "KIWOOM DRX",
    }
    assert all(by_code[code]["roster_status"] == "official" for code in expected_counts)
    assert all(by_code[code]["official_source_url"].startswith("https://") for code in expected_counts)
    assert by_code["WORLDS"]["roster_status"] == "not_published"

def test_dashboard_assets_include_requested_metrics():
    js = client.get("/static/js/app.js").text
    assert "Torretas destruidas" in js
    assert "Inhibidores destruidos" in js
    assert "Dragones asesinados" in js
    assert "Barones asesinados" in js
    assert "Oro total" in js
    assert "Porcentaje de victorias" in js
    assert "Cuotas justas estimadas" in js
    assert "Valor · últimas 5 series" in js
    assert "solo_kills_status" not in js
    assert "Solo kills" not in js
    assert "CS promedio por mapa" in js
    assert "Asesinatos promedio por mapa" in js
    assert "Muertes promedio por mapa" in js
    assert "player.kills_per_map" in js
    assert "player.deaths_per_map" in js
    assert "cs_per_map" in js
    assert "loadPreviewOdds" in js
    assert "data-odds-key" in js
    assert "Cuotas calculadas no disponibles" in js



def test_known_aliases_reconcile_renamed_teams():
    from datetime import datetime, timezone
    from sqlmodel import Session, select
    from app.database import engine
    from app.models_lol import LolMatchEvent
    from app.services.lol_team_aliases import canonical_team, synchronize_known_aliases

    with Session(engine) as session:
        session.add(LolMatchEvent(
            match_key="alias-sync-agal", source_name="test", source_match_id="alias-sync-agal",
            league="EWC", tournament="EWC", team_a="AG.AL", team_b="T1",
            start_time_utc=datetime(2026, 8, 1, tzinfo=timezone.utc), status="scheduled",
        ))
        session.commit()
        result = synchronize_known_aliases(session)
        assert canonical_team(session, "AG.AL") == "Anyone's Legend"
        assert canonical_team(session, "LYON (2024 American Team)") == "LYON"
        assert canonical_team(session, "Ninjas in Pyjamas.CN") == "Ninjas in Pyjamas"
        assert result["exhibitions"][0]["alias"] == "CNB Legends"
        event = session.exec(select(LolMatchEvent).where(LolMatchEvent.match_key == "alias-sync-agal")).one()
        assert event.team_a == "Anyone's Legend"


def test_sources_support_configuration_and_custom_api():
    from app.config import settings

    headers = {"X-Admin-Token": settings.admin_token}
    configured = client.put(
        "/api/sources/external_odds_api/configuration",
        headers=headers,
        json={"base_url": "https://example.com/api", "api_key": "secret", "enabled": True},
    )
    assert configured.status_code == 200
    assert configured.json()["api_key_configured"] is True
    assert "secret" not in configured.text
    created = client.post(
        "/api/sources/custom",
        headers=headers,
        json={"display_name": "Stats API Test", "base_url": "https://example.com/stats", "enabled": True},
    )
    assert created.status_code == 200
    assert created.json()["custom"] is True
    assert any(item["code"] == created.json()["code"] for item in client.get("/api/sources").json()["sources"])


def test_manual_odds_upload_and_match_response(tmp_path):
    from datetime import datetime, timezone
    from sqlmodel import Session
    from app.config import settings
    from app.database import engine
    from app.models_lol import LolMatchEvent

    with Session(engine) as session:
        session.add(LolMatchEvent(
            match_key="odds-test-match", source_name="test", source_match_id="odds-test",
            league="LCK/2026 Season", tournament="LCK", team_a="Alpha", team_b="Beta",
            start_time_utc=datetime(2026, 12, 1, tzinfo=timezone.utc), status="scheduled",
        ))
        session.commit()
    original = settings.lol_odds_import_dir
    settings.lol_odds_import_dir = str(tmp_path / "odds")
    try:
        csv_data = (
            "match_key,team_name,decimal_odds,provider,captured_at\n"
            "odds-test-match,Alpha,1.80,manual,2026-07-15T12:00:00Z\n"
            "odds-test-match,Beta,2.10,manual,2026-07-15T12:00:00Z\n"
        )
        response = client.post(
            "/api/sources/odds/upload",
            headers={"X-Admin-Token": settings.admin_token},
            files={"file": ("odds.csv", csv_data, "text/csv")},
        )
        assert response.status_code == 200
        assert response.json()["inserted"] == 2
        match = client.get("/api/lol/matches/odds-test-match").json()
        assert match["odds_available"] is True
        assert match["odds_a"] == 1.8
        assert match["odds_b"] == 2.1
    finally:
        settings.lol_odds_import_dir = original


def test_alias_identity_wins_over_conflicting_mapping():
    from sqlmodel import Session
    from app.database import engine
    from app.models_lol import LolTeamAlias
    from app.services.lol_team_aliases import canonical_team
    with Session(engine) as session:
        session.add(LolTeamAlias(canonical_team="Academy", alias="Identity Test", normalized_alias="academy"))
        session.add(LolTeamAlias(canonical_team="Identity Test", alias="Identity Test", normalized_alias="identitytest"))
        session.commit()
        assert canonical_team(session, "Identity Test") == "Identity Test"


def test_oracle_replacement_updates_and_removes_stale_games(tmp_path):
    from sqlmodel import Session, select
    from app.database import engine
    from app.models_lol import LolGameHistory, LolPlayerGameStat, LolTeamGameStat
    from app.services.imports.oracles_elixir_importer import _import_csv_file

    header = "gameid,position,playername,teamname,side,date,league,result,towers,inhibitors,kills,deaths,assists,dragons,barons,totalgold,total cs\n"
    def game(game_id, towers, cs):
        return (
            f"{game_id},team,,Alpha,Blue,2099-01-01,LCK,1,{towers},1,12,8,20,3,1,60000,0\n"
            f"{game_id},team,,Beta,Red,2099-01-01,LCK,0,4,0,8,12,14,1,0,50000,0\n"
            f"{game_id},top,AlphaTop,Alpha,Blue,2099-01-01,LCK,1,0,0,3,1,4,0,0,12000,{cs}\n"
            f"{game_id},top,BetaTop,Beta,Red,2099-01-01,LCK,0,0,0,1,3,2,0,0,10000,200\n"
        )

    first = tmp_path / "history.csv"
    first.write_text(header + game("replace-1", 6, 250) + game("replace-stale", 5, 220), encoding="utf-8")
    newest = tmp_path / "history-new.csv"
    newest.write_text(header + game("replace-1", 11, 333), encoding="utf-8")
    with Session(engine) as session:
        assert _import_csv_file(session, str(first), replace=True)["games"] == 2
        assert _import_csv_file(session, str(newest), replace=True)["games"] == 1
        games = session.exec(select(LolGameHistory).where(LolGameHistory.year == 2099)).all()
        assert [item.source_game_id for item in games] == ["replace-1"]
        game_id = games[0].id
        alpha = session.exec(select(LolTeamGameStat).where(
            LolTeamGameStat.game_id == game_id, LolTeamGameStat.team_name == "Alpha"
        )).one()
        player = session.exec(select(LolPlayerGameStat).where(
            LolPlayerGameStat.game_id == game_id, LolPlayerGameStat.player_name == "AlphaTop"
        )).one()
        assert alpha.towers == 11
        assert player.cs == 333


def test_estimated_market_uses_both_teams_recent_series():
    from app.services.lol_metrics_engine import _estimated_market

    team_a = {"series_wins": 4, "series_losses": 1}
    team_b = {"series_wins": 2, "series_losses": 3}
    market = _estimated_market(team_a, team_b, "Alpha", "Beta")
    assert market["available"] is True
    assert market["team_a"]["probability_pct"] == 62.5
    assert market["team_b"]["probability_pct"] == 37.5
    assert market["team_a"]["decimal_odds"] == 1.6
    assert market["team_b"]["decimal_odds"] == 2.67
    assert market["team_a"]["series_used"] == 5
    assert market["team_b"]["series_used"] == 5
