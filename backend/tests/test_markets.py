from fastapi.testclient import TestClient

from app.main import app
from app.services import market_catalog as catalog
from app.services.market_mapper import map_market, normalize_text

client = TestClient(app)


def test_normalize_removes_accents_and_case():
    assert normalize_text("Total de Goles") == "total de goles"
    assert normalize_text("Más de 2.5") == "mas de 2.5"
    assert normalize_text("") == ""


def test_catalog_has_football_markets():
    codes = set(catalog.FOOTBALL_MARKETS)
    assert "match_winner" in codes
    assert "total_goals_over_under" in codes
    assert "both_teams_to_score" in codes


def test_catalog_has_lol_markets():
    codes = set(catalog.LOL_MARKETS)
    assert "map_winner" in codes
    assert "total_kills_over_under" in codes
    assert "game_duration_over_under" in codes


def test_seed_endpoint():
    resp = client.post("/markets/seed")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    # Seeding is idempotent and may run before this test (shared DB / startup),
    # so assert the catalog is populated rather than the upsert count.
    markets = client.get("/markets").json()
    assert len(markets) > 20
    assert any(m["sport"] == "football" for m in markets)
    assert any(m["sport"] == "lol" for m in markets)
    # Idempotent: a second call inserts nothing new.
    again = client.post("/markets/seed").json()
    assert again["markets_upserted"] == 0


def test_markets_endpoint():
    resp = client.get("/markets")
    assert resp.status_code == 200
    markets = resp.json()
    assert isinstance(markets, list)
    assert len(markets) > 10
    codes = {m["market_code"] for m in markets}
    assert "match_winner" in codes
    assert "map_winner" in codes


def test_aliases_endpoint():
    resp = client.get("/markets/aliases")
    assert resp.status_code == 200


def test_mapper_maps_spanish_alias():
    # Must call seed first so tables are populated.
    client.post("/markets/seed")
    from app.database import Session, engine

    with Session(engine) as session:
        mid, code = map_market(session, "football", "Total de goles")
        assert code == "total_goals_over_under"
        assert mid is not None

        mid2, code2 = map_market(session, "lol", "Total de torretas destruidas")
        assert code2 == "total_towers_over_under"


def test_unmapped_returns_none():
    client.post("/markets/seed")
    from app.database import Session, engine

    with Session(engine) as session:
        mid, code = map_market(session, "football", "Mercado Rarisimo Inexistente XYZ")
        assert mid is None
