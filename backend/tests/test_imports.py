from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _upload(url: str, filename: str):
    data = (FIXTURES / filename).read_bytes()
    return client.post(url, files={"file": (filename, data, "text/csv")})


def test_templates_downloadable():
    r1 = client.get("/imports/templates/aposta-odds")
    assert r1.status_code == 200
    assert "text/csv" in r1.headers["content-type"]
    r2 = client.get("/imports/templates/oracles-elixir")
    assert r2.status_code == 200


def test_aposta_valid_import():
    client.post("/markets/seed")
    r = _upload("/imports/aposta-odds-csv", "aposta_odds_sample.csv")
    assert r.status_code == 200
    batch = r.json()
    assert batch["status"] in ("success", "partial")
    assert batch["imported_rows"] >= 5
    # imported odds should be retrievable and at least one mapped to a market code
    odds = client.get("/odds/imported").json()
    assert len(odds) >= 5
    mapped = [o for o in odds if o["market_code"] == "total_goals_over_under"]
    assert mapped


def test_aposta_invalid_rows_do_not_abort():
    client.post("/markets/seed")
    r = _upload("/imports/aposta-odds-csv", "aposta_odds_invalid_rows.csv")
    assert r.status_code == 200
    batch = r.json()
    # One row has empty team_a, one has odds <= 1 -> errors; one unknown market -> unmapped warning.
    assert batch["error_rows"] >= 2
    assert batch["imported_rows"] >= 1  # valid rows still imported
    assert batch["status"] == "partial"
    errors = client.get(f"/imports/batches/{batch['id']}/errors").json()
    assert len(errors) >= 2


def test_aposta_unknown_market_is_unmapped_not_fatal():
    client.post("/markets/seed")
    r = _upload("/imports/aposta-odds-csv", "aposta_odds_invalid_rows.csv")
    assert r.status_code == 200
    odds = client.get("/odds/imported").json()
    unmapped = [o for o in odds if o["market_text"] == "Mercado Rarisimo Inexistente"]
    # The unknown-market row imports with market_id null (unmapped), not rejected.
    assert all(o["market_id"] is None for o in unmapped)


def test_oracles_import_team_and_player_rows():
    r = _upload("/imports/oracles-elixir-csv", "oracles_elixir_sample.csv")
    assert r.status_code == 200
    batch = r.json()
    assert batch["status"] in ("success", "partial")
    assert batch["imported_rows"] >= 4  # 2 player + 2 team rows


def test_batches_listed():
    _upload("/imports/aposta-odds-csv", "aposta_odds_sample.csv")
    batches = client.get("/imports/batches").json()
    assert len(batches) >= 1
    assert batches[0]["id"] >= 1


def test_imports_ui():
    assert client.get("/imports/ui").status_code == 200


def test_markets_ui():
    assert client.get("/markets/ui").status_code == 200
