from fastapi.testclient import TestClient

from app.main import app
from app.services import source_resolver

client = TestClient(app)

# Synthetic, always-enabled sources for deterministic ordering tests.
SYNTHETIC = [
    {
        "slug": "low",
        "sport": "football",
        "use_for": ["teams"],
        "rank": 50,
        "enabled_by_default": True,
        "requires_env": None,
    },
    {
        "slug": "high",
        "sport": "football",
        "use_for": ["teams"],
        "rank": 80,
        "enabled_by_default": True,
        "requires_env": None,
    },
]


def test_resolver_picks_highest_rank_enabled():
    primary = source_resolver.pick_primary("football", "teams", SYNTHETIC)
    assert primary["slug"] == "high"


def test_resolver_fallback_chain():
    chain = source_resolver.fallback_chain("football", "teams", SYNTHETIC)
    assert [s["slug"] for s in chain] == ["low"]


def test_resolver_should_not_overwrite_higher_with_lower():
    assert source_resolver.should_update(90, 85, existing_has_value=True) is False
    assert source_resolver.should_update(85, 90, existing_has_value=True) is True
    assert source_resolver.should_update(90, 70, existing_has_value=False) is True


def test_resolver_env_gating(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    assert source_resolver.pick_primary("football", "teams")["slug"] == "openligadb"
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "dummy-key")
    assert source_resolver.pick_primary("football", "teams")["slug"] == "football_data_org"


def test_sources_endpoint():
    response = client.get("/sources")
    assert response.status_code == 200
    slugs = [s["slug"] for s in response.json()]
    assert "openligadb" in slugs
    assert "riot_datadragon" in slugs


def test_football_data_org_is_primary_when_key_present(monkeypatch):
    monkeypatch.setenv("FOOTBALL_DATA_API_KEY", "dummy-key")
    rows = client.get("/sources/capabilities").json()
    fixtures = [r for r in rows if r["sport"] == "football" and r["data_type"] == "fixtures"]
    primary = [r for r in fixtures if r["is_primary"]]
    assert len(primary) == 1
    assert primary[0]["source_slug"] == "football_data_org"
    # OpenLigaDB must be present but NOT primary while the key exists.
    openliga = [r for r in fixtures if r["source_slug"] == "openligadb"]
    assert openliga and openliga[0]["is_primary"] is False


def test_openligadb_is_primary_without_key(monkeypatch):
    monkeypatch.delenv("FOOTBALL_DATA_API_KEY", raising=False)
    rows = client.get("/sources/capabilities").json()
    fixtures = [r for r in rows if r["sport"] == "football" and r["data_type"] == "fixtures"]
    primary = [r for r in fixtures if r["is_primary"]]
    assert primary and primary[0]["source_slug"] == "openligadb"


def test_rankings_endpoint():
    response = client.get("/sources/rankings")
    assert response.status_code == 200
    data = response.json()
    assert "football" in data
    assert "lol" in data
    football_ranks = [s["rank"] for s in data["football"]]
    assert football_ranks == sorted(football_ranks, reverse=True)
    lol_slugs = [s["slug"] for s in data["lol"]]
    assert "riot_datadragon" in lol_slugs


def test_capabilities_endpoint():
    response = client.get("/sources/capabilities")
    assert response.status_code == 200
    rows = response.json()
    assert any(row["data_type"] == "champions" for row in rows)
    assert any(row["is_primary"] for row in rows)


def test_seed_endpoint():
    response = client.post("/sources/seed")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["sources_upserted"] >= 10
    assert body["capabilities_upserted"] > 0
    # Idempotent: running again keeps the same source count.
    again = client.post("/sources/seed").json()
    assert again["sources_upserted"] == body["sources_upserted"]


def test_sources_ui():
    response = client.get("/sources/ui")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "ranking de fuentes" in response.text
