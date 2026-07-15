# Testing

## Test Structure

```
backend/tests/
├── conftest.py           # Test setup: temp SQLite DB, init_db()
├── test_health.py        # Health, sources API, removed-domain checks
├── test_pages.py         # HTML pages, API endpoints, static assets
└── test_timezone.py      # Timezone conversion tests
```

**Run tests:**
```bash
cd backend
pytest -v
```

**Test framework:** pytest 9.1.1 with `httpx` for FastAPI `TestClient`.

## Conftest Setup

**Source:** `backend/tests/conftest.py`

The conftest creates a **temporary SQLite database** in the system temp directory:

1. Sets `DATABASE_URL` to a temp file path before any app code is imported
2. Removes any existing temp DB
3. Imports and runs `init_db()` to create tables
4. All models from `models_lol` are registered

**Important:** The conftest does NOT use pytest fixtures — it runs at import time. This means test order is sequential and shared state persists across tests. Each test should be self-contained or clean up after itself.

## Key Tests

### test_health.py

| Test | What it validates |
|------|-------------------|
| `test_health()` | `GET /health` returns `{"status": "ok"}` |
| `test_docs()` | FastAPI `/docs` returns 200 |
| `test_sources_api()` | `/api/sources` returns configured sources |
| `test_removed_domains_stay_removed()` | Legacy routes (`/odds/analyze`, `/combo/analyze`) return 404 |

### test_pages.py

| Test | What it validates |
|------|-------------------|
| `test_dashboard_html()` | `/` renders competitive title, live clock |
| `test_sources_html_has_upload_flow()` | `/sources` has preview/save buttons, upload validation |
| `test_match_detail_html()` | `/lol/matches/{key}` renders loading state, estimated market heading, `market-source-badge` |
| `test_upcoming_api()` | `/api/lol/matches/upcoming` returns correct window_hours |
| `test_upcoming_timezone()` | API response contains `America/Asuncion` timezone |
| `test_match_not_found()` | Non-existent match returns 404 |
| `test_static_assets()` | CSS serves Inter font; JS includes `el("live-clock")`; Inter font file served |
| `test_competition_classifier_excludes_academies()` | Academy leagues (LCK CL) excluded; LTA North→LCS, LTA South→CBLOL mapping verified; bare LTA returns None |
| `test_upcoming_api_exposes_only_allowed_competitions()` | Only 10 competition codes appear (LCS, CBLOL replace LTA) |
| `test_dashboard_assets_include_requested_metrics()` | JS contains expected display strings including `loadPreviewOdds`, `data-odds-key`, `"Cuotas calculadas no disponibles"` (replaces previous `"Sin cuotas capturadas"`), plus win rate, estimated odds, per-map labels |
| `test_manual_odds_upload_and_match_response()` | Full odds upload → API response integration test |
| `test_estimated_market_uses_both_teams_recent_series()` | `_estimated_market(4-1, 2-3)` returns p=62.5%, odds=1.60 / 2.67 with Laplace smoothing |
| `test_2026_official_competition_rosters_are_complete()` | 2026 rosters: counts (LCK=10, LPL=14, LEC=10, LCS=8, CBLOL=8, LCP=8, MSI=11, FIRST_STAND=8, EWC=16), all `roster_status="official"` except WORLDS (`not_published`), LCK teams match published list |
| `test_known_aliases_reconcile_renamed_teams()` | `synchronize_known_aliases()` maps AG.AL→Anyone’s Legend, LYON→LYON, Ninjas in Pyjamas.CN→Ninjas in Pyjamas; match event team_a updated; exhibition teams returned |
| `test_sources_support_configuration_and_custom_api()` | PUT source configuration stores base_url/api_key/enabled via admin token; custom source POST creates new DataSource listed in /api/sources; api_key_configured is true but secret not in response |

### test_timezone.py

| Test | What it validates |
|------|-------------------|
| `test_app_timezone_is_asuncion()` | Default timezone is America/Asuncion |
| `test_to_local_applies_minus_three_offset()` | UTC→local conversion applies -03:00 offset |
| `test_offset_and_format()` | `offset_str()` and `format_local()` produce correct strings |

## Writing Tests

**Patterns to follow:**

1. Use `TestClient(app)` from `app.main` — already imported in test files
2. DB is pre-initialized — create model instances directly with `Session(engine)`
3. Test competition classifier by importing `_competition_code` from `app.routers.lol_api`
4. Static assets are served from `app/static/` — verify via HTTP response

**Patterns to avoid:**

- Don't mock the database — tests run against a real SQLite temp file
- Don't assume test isolation — the conftest does not wrap tests in transactions
- Don't test legacy removed endpoints (football, betting) — they return 404

## Coverage Areas Not Yet Tested

- **Series builder** (`services/series_builder.py`) — No dedicated test
- **Odds importer** — Tested in test_pages.py for one scenario
- **Worker jobs** — No scheduler tests
