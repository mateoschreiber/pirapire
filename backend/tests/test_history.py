from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_odds_analyze_save_creates_prediction():
    resp = client.post(
        "/odds/analyze",
        json={
            "odds_decimal": 2.0,
            "model_probability": 0.55,
            "save": True,
            "sport": "football",
            "match_label": "Arsenal vs Chelsea",
            "market_text": "Total de goles Over 2.5",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["prediction_id"] is not None

    predictions = client.get("/history/predictions").json()
    ids = [p["id"] for p in predictions]
    assert body["prediction_id"] in ids


def test_odds_analyze_without_save_has_no_prediction():
    resp = client.post("/odds/analyze", json={"odds_decimal": 2.0})
    assert resp.status_code == 200
    assert resp.json()["prediction_id"] is None


def test_combo_analyze_save_creates_combo_and_legs():
    resp = client.post(
        "/combo/analyze",
        json={
            "save": True,
            "name": "Combo test",
            "sport": "football",
            "legs": [
                {"probability": 0.5, "odds_decimal": 2.1, "market_text": "Match winner"},
                {"probability": 0.5, "odds_decimal": 2.0, "market_text": "Over 2.5"},
            ],
        },
    )
    assert resp.status_code == 200
    combo_id = resp.json()["combo_id"]
    assert combo_id is not None

    combos = client.get("/history/combos").json()
    match = [c for c in combos if c["combo"]["id"] == combo_id]
    assert match
    assert len(match[0]["legs"]) == 2


def test_settle_prediction():
    created = client.post(
        "/odds/analyze", json={"odds_decimal": 2.0, "save": True}
    ).json()
    pid = created["prediction_id"]
    resp = client.post(f"/history/predictions/{pid}/settle", json={"result": "won"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["result"] == "won"
    assert body["status"] == "settled"


def test_settle_combo():
    created = client.post(
        "/combo/analyze",
        json={"save": True, "legs": [{"probability": 0.6, "odds_decimal": 1.8}]},
    ).json()
    cid = created["combo_id"]
    resp = client.post(f"/history/combos/{cid}/settle", json={"result": "lost"})
    assert resp.status_code == 200
    assert resp.json()["result"] == "lost"


def test_settle_invalid_result():
    created = client.post("/odds/analyze", json={"odds_decimal": 2.0, "save": True}).json()
    pid = created["prediction_id"]
    resp = client.post(f"/history/predictions/{pid}/settle", json={"result": "bogus"})
    assert resp.status_code == 400


def test_history_ui_not_placeholder():
    html = client.get("/history/ui").text
    assert client.get("/history/ui").status_code == 200
    assert "Predicciones individuales" in html
    assert "placeholder" not in html.lower()
