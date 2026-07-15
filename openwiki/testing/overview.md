# Testing

## Test infrastructure

**Config:** `backend/pytest.ini` — sets `pythonpath = .` and `testpaths = tests`

**Runner:** `pytest -q` (CI via GitHub Actions on push/PR, Python 3.12)

**Linter:** `ruff check .`

## Test database

`backend/tests/conftest.py` creates a temporary SQLite database per test session:

```python
_tmp_dir = Path(tempfile.mkdtemp(prefix="pirapire_test_"))
_tmp_db = _tmp_dir / "pirapire_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp_db}"
```

- Environment variables are set to disable live ingestion and bootstrap checks
- `init_db()` runs once at module load, creating all tables
- Cleanup via `atexit.register(_cleanup)` removes temp files

## Test fixtures

Static test data in `backend/tests/fixtures/`:

| Fixture | Used by |
|---------|---------|
| `aposta_odds_sample.csv` | `test_imports.py` |
| `aposta_odds_invalid_rows.csv` | `test_imports.py` |
| `football_data_matches.json` | `test_football_data_org.py` |
| `football_data_standings.json` | `test_football_data_org.py` |
| `datadragon_versions.json` | `test_phase0d_clients.py` |
| `datadragon_champion.json` | `test_phase0d_clients.py` |
| `oracles_elixir_sample.csv` | `test_imports.py` |

## Test categories

### Connectors / Sources (7 files)

| Test file | What it covers |
|-----------|---------------|
| `test_connectors.py` (5K) | General connector interface, source discovery |
| `test_sources.py` (4K) | Source registry and resolution |
| `test_football_data_org.py` (6K) | football-data.org client: auth, normalization, 429 retry |
| `test_phase0d_clients.py` (4.5K) | DataDragon, Riot API, TheSportsDB, OpenLigaDB clients |
| `test_api_football_verification.py` (1.5K) | API-Football credential verification |
| `test_sync_endpoints.py` (3K) | Sync endpoint contracts |
| `test_integration_settings.py` (16K) | Auth, credential CRUD, encryption, provider state, audit log |

### Ingestion Pipeline (6 files)

| Test file | Phase |
|-----------|-------|
| `test_phase4b_ingestion.py` | Phase 4B: ingestion gate |
| `test_phase4b1_ingestion.py` (4.6K) | Phase 4B1: bounded ingestion for active participants |
| `test_phase4b2_freshness.py` (5.9K) | Phase 4B2: freshness marking, series completion |
| `test_phase4b3_lol_map_facts.py` (6.3K) | Phase 4B3: LoL map/player facts |
| `test_phase4b4_fresh_football.py` (4.5K) | Phase 4B4: fresh football window |
| `test_phase4b41_history_cutoff.py` (4.4K) | Phase 4B41: strict per-event history window |

### Recommender & Odds (4 files)

| Test file | What it covers |
|-----------|---------------|
| `test_recommender.py` (4.4K) | Ranking modes, combo builder constraints |
| `test_odds_engine.py` (1.8K) | Odds probability calculations, risk labels |
| `test_market_matcher.py` | Market name matching |
| `test_event_matcher.py` | Event identity matching |

### Descriptive Stats & Events (3 files)

| Test file | What it covers |
|-----------|---------------|
| `test_phase4c_descriptive.py` (11.8K — largest test) | Mean/WDL football stats, LoL stats, end-to-end seeding and querying |
| `test_phase4d1_active_events.py` (4.5K) | Event lifecycle states, refresh queue |
| `test_phase2_identity.py` (4K) | Event identity and snapshot activation |

### General / Integration (10+ files)

| Test file | What it covers |
|-----------|---------------|
| `test_health.py` | Healthcheck endpoint |
| `test_pages.py` (3.6K) | UI page rendering |
| `test_dashboard_state.py` (2.3K) | Dashboard state management |
| `test_imports.py` (2.8K) | CSV import (valid/invalid rows, partial batches) |
| `test_markets.py` (2.6K) | Market catalog |
| `test_history.py` (2.9K) | Betting history CRUD |
| `test_aposta_sync.py`, `test_aposta.py`, `test_aposta_snapshot.py` | Aposta sync and snapshot |
| `test_phase3_no_vig.py` | No-vig probability calculation |
| `test_portability.py` (2.8K) | Cross-platform path handling |
| `test_timezone.py` | Timezone display |
| `test_phase0_containment.py` | Source containment |
| `test_fase4_guardrails.py` | Guardrails / safety checks |

## Running tests

```bash
# From inside backend/
cd backend
pytest -q                          # All tests
pytest -q tests/test_recommender.py  # Specific file
pytest -q -k "football"            # Filter by keyword

# With linting
ruff check .
```

## Test patterns

- **HTTP tests:** FastAPI `TestClient` against `app.main:app`, with temp SQLite
- **Service tests:** Direct function calls with `Session` from temp DB
- **Source tests:** Mocked HTTP responses or environment-gated live tests
- **No factory fixtures:** Tests create their own data as needed; `conftest.py` only provides DB setup
- **Database isolation:** Temp SQLite per session (not per test), cleaned up on exit
