import pytest


class _Response:
    def __init__(self, chunks, url="https://example.test/history.csv"):
        self._chunks = chunks
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def raise_for_status(self):
        return None

    def iter_content(self, chunk_size):
        return iter(self._chunks)


def test_google_drive_share_link_becomes_direct_download_url():
    from app.services.imports.remote_oracles_elixir import google_drive_download_url

    assert google_drive_download_url(
        "https://drive.google.com/file/d/1hnpbrUpBMS1TZI7IovfpKeZfWJH1Aptm/view?usp=drive_link"
    ) == (
        "https://drive.usercontent.google.com/download?"
        "id=1hnpbrUpBMS1TZI7IovfpKeZfWJH1Aptm&export=download&confirm=t"
    )


def test_remote_csv_is_downloaded_and_validated(monkeypatch, tmp_path):
    from app.services.imports.remote_oracles_elixir import download_remote_csv

    payload = b"gameid,position,teamname\ngame-1,team,Alpha\n"
    monkeypatch.setattr(
        "app.services.imports.remote_oracles_elixir.requests.get",
        lambda *args, **kwargs: _Response([payload]),
    )

    target = tmp_path / "history.csv"
    checksum, size, final_url = download_remote_csv("https://example.test/history.csv", target, 1024)

    assert size == len(payload)
    assert len(checksum) == 64
    assert final_url == "https://example.test/history.csv"
    assert target.read_bytes() == payload


def test_remote_csv_reports_google_drive_quota(monkeypatch, tmp_path):
    from app.services.imports.remote_oracles_elixir import RemoteCsvError, download_remote_csv

    monkeypatch.setattr(
        "app.services.imports.remote_oracles_elixir.requests.get",
        lambda *args, **kwargs: _Response([b"<html>Google Drive - Quota exceeded</html>"]),
    )

    with pytest.raises(RemoteCsvError, match="cuota excedida"):
        download_remote_csv("https://drive.google.com/file/d/file-id/view", tmp_path / "history.csv", 1024)


def test_oracle_remote_sync_can_be_queued():
    from app.config import settings
    from app.routers.sources import _source
    from app.database import engine
    from fastapi.testclient import TestClient
    from sqlmodel import Session
    from app.main import app

    original_token = settings.admin_token
    settings.admin_token = "test-admin"
    try:
        with Session(engine) as session:
            source = _source(session, "oracles_elixir")
            source.config_json = '{"base_url":"https://drive.google.com/file/d/file-id/view"}'
            source.enabled = True
            session.add(source)
            session.commit()
        response = TestClient(app).post(
            "/api/sources/oracles_elixir/sync",
            headers={"X-Admin-Token": "test-admin"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "queued"
    finally:
        settings.admin_token = original_token


def test_oracle_automatic_refresh_can_be_disabled():
    from app.config import settings
    from app.main import app
    from fastapi.testclient import TestClient

    original_token = settings.admin_token
    settings.admin_token = "test-admin"
    try:
        client = TestClient(app)
        response = client.put(
            "/api/sources/oracles_elixir/configuration",
            headers={"X-Admin-Token": "test-admin"},
            json={
                "base_url": "https://drive.google.com/file/d/file-id/view",
                "enabled": True,
                "auto_refresh": False,
            },
        )
        assert response.status_code == 200
        assert response.json()["auto_refresh"] is False
        assert client.post(
            "/api/sources/oracles_elixir/sync",
            headers={"X-Admin-Token": "test-admin"},
        ).status_code == 409
    finally:
        settings.admin_token = original_token


def test_incremental_oracle_import_adds_only_new_games(tmp_path):
    from app.database import engine
    from app.models_lol import LolGameHistory
    from app.services.imports.oracles_elixir_importer import _import_csv_file
    from sqlmodel import Session, select

    header = "gameid,position,teamname,side,date,league,result\n"
    game_one = "incremental-1,team,Alpha,Blue,2031-01-01,LCK,1\n" "incremental-1,team,Beta,Red,2031-01-01,LCK,0\n"
    game_two = "incremental-2,team,Gamma,Blue,2031-01-02,LCK,1\n" "incremental-2,team,Delta,Red,2031-01-02,LCK,0\n"
    initial = tmp_path / "initial.csv"
    updated = tmp_path / "updated.csv"
    initial.write_text(header + game_one, encoding="utf-8")
    updated.write_text(header + game_one + game_two, encoding="utf-8")

    with Session(engine) as session:
        assert _import_csv_file(session, str(initial), replace=False)["games"] == 1
        assert _import_csv_file(session, str(updated), replace=False)["games"] == 1
        games = session.exec(select(LolGameHistory).where(
            LolGameHistory.source_game_id.in_(["incremental-1", "incremental-2"])
        )).all()
        assert {game.source_game_id for game in games} == {"incremental-1", "incremental-2"}


def test_incremental_oracle_import_updates_present_games_without_pruning(tmp_path):
    from app.database import engine
    from app.models_lol import LolGameHistory, LolTeamGameStat
    from app.services.imports.oracles_elixir_importer import _import_csv_file
    from sqlmodel import Session, select

    header = "gameid,position,teamname,side,date,league,result,towers\n"
    original = tmp_path / "original.csv"
    changed = tmp_path / "changed.csv"
    original.write_text(
        header
        + "update-1,team,Alpha,Blue,2032-01-01,LCK,1,5\n"
        + "update-1,team,Beta,Red,2032-01-01,LCK,0,3\n"
        + "preserved-1,team,Gamma,Blue,2032-01-02,LCK,1,7\n"
        + "preserved-1,team,Delta,Red,2032-01-02,LCK,0,2\n",
        encoding="utf-8",
    )
    changed.write_text(
        header + "update-1,team,Alpha,Blue,2032-01-01,LCK,1,11\n" + "update-1,team,Beta,Red,2032-01-01,LCK,0,3\n",
        encoding="utf-8",
    )

    with Session(engine) as session:
        _import_csv_file(session, str(original), replace=False)
        _import_csv_file(session, str(changed), replace=True, prune_missing=False)
        preserved = session.exec(select(LolGameHistory).where(LolGameHistory.source_game_id == "preserved-1")).one()
        updated = session.exec(select(LolGameHistory).where(LolGameHistory.source_game_id == "update-1")).one()
        alpha = session.exec(select(LolTeamGameStat).where(
            LolTeamGameStat.game_id == updated.id, LolTeamGameStat.team_name == "Alpha"
        )).one()
        assert preserved is not None
        assert alpha.towers == 11
