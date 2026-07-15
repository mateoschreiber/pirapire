# Architecture

## System overview

Pirapire is a single-repository, three-service Docker Compose application. All services share the same SQLite database file via a Docker volume mount.

```
┌────────────────────────────────────────────────────────┐
│  Docker Compose                                        │
│                                                        │
│  ┌──────────────┐   ┌──────────────┐   ┌────────────┐ │
│  │ pirapire_app │   │pirapire_worker│   │pirapire_    │ │
│  │  (FastAPI)   │   │ (APScheduler) │   │  browser    │ │
│  │  :8000→:8090 │   │  same image   │   │ (Playwright)│ │
│  └──────┬───────┘   └──────┬───────┘   └──────┬─────┘ │
│         │                  │                   │        │
│         └──────────────────┼───────────────────┘        │
│                            │                            │
│                    ┌───────┴───────┐                    │
│                    │  SQLite DB    │                    │
│                    │ data/pirapire │                    │
│                    │    .db        │                    │
│                    └───────────────┘                    │
└────────────────────────────────────────────────────────┘
```

## Docker services

### `pirapire_app` (main application)

- **Image:** built from `backend/Dockerfile` (Python 3.12-slim)
- **Command:** `uvicorn app.main:app --host 0.0.0.0 --port 8000`
- **Port:** internal 8000 → host `${PIRAPIRE_PORT:-8090}`
- **Volumes:** `./data:/app/data` (SQLite), `./logs:/app/logs`, `.env` mounted as secret at `/run/secrets/pirapire.env`
- **Healthcheck:** `curl http://localhost:8000/health`
- **Source:** `docker-compose.yml`

### `pirapire_worker` (background scheduler)

- **Image:** same as `pirapire_app` (build once, reuse)
- **Command:** `python -u /app/app/worker_main.py`
- **Depends on:** `pirapire_app` (startup ordering)
- **Scheduler:** APScheduler `BackgroundScheduler` with `coalesce=True` and `max_instances=1`
- **Jobs:** 6 periodic tasks (see [operations runbook](../operations/runbook.md))
- **Source:** `backend/app/worker_main.py`

### `pirapire_browser` (browser automation)

- **Image:** built from `browser-worker/Dockerfile` (Playwright + Chromium)
- **Port:** internal 8080 (not published to host)
- **Purpose:** renders JavaScript-heavy pages (SofaScore, Aposta.LA) for data extraction
- **Used by:** `fresh_football.py` (SofaScore fallback), `browser_fallback.py`
- **Source:** `browser-worker/browser_worker.py`

## Tech stack detail

| Layer | Technology | Key modules |
|-------|-----------|-------------|
| Web framework | FastAPI 0.139 | `app/main.py` |
| ASGI server | Uvicorn 0.51 | `Dockerfile` |
| ORM | SQLModel 0.0.39 / SQLAlchemy | `app/database.py`, `app/models*.py` |
| Database | SQLite (WAL journal mode) | `/app/data/pirapire.db` |
| Templates | Jinja2 3.1 | `app/templates/*.html` (18 files) |
| HTTP client | httpx 0.28 | `app/services/http_client.py` |
| Scheduler | APScheduler 3.10 | `app/worker_main.py` |
| Encryption | cryptography (Fernet) | `app/services/secret_provider.py` |
| Browser automation | Playwright (separate service) | `browser-worker/browser_worker.py` |
| Config | pydantic-settings 2.14 | `app/config.py` |

## Application lifecycle

`main.py` uses FastAPI's `lifespan` context manager:

1. `init_db()` — creates all tables via `SQLModel.metadata.create_all()`, runs migration functions, backfills canonical identity
2. `seed_markets_safe()` — idempotent seeding of market catalog (ES/EN aliases)
3. `seed_lol_catalog_safe()` — idempotent seeding of LoL league catalog

The worker calls `init_db()` on startup separately since it runs in its own container.

## Router architecture

19 routers registered in `main.py`. Most serve both JSON API endpoints and HTML templates where applicable:

| Router | Prefix | Type | Purpose |
|--------|--------|------|---------|
| `health.py` | — | API | `/health`, `/api/info` |
| `pages.py` | — | UI | All HTML pages via Jinja2 (`include_in_schema=False`) |
| `events.py` | `/api/events` | API | Event detail, no-vig stats, legacy ID redirects |
| `aposta.py` | `/api/aposta` | API | Aposta.LA sync, odds browsing, snapshot management |
| `odds.py` | `/odds` | API | Single-odds analysis |
| `combo.py` | `/combo` | API | Combo/parlay analysis |
| `recommendations.py` | `/api/recommendations` | API | Run recommendations, list bets/combos |
| `sources.py` | `/api/sources` | API | External source sync (football, LoL) |
| `source_runs.py` | — | API | Sync run history |
| `data.py` | `/data` | API | Football/LoL data browsing |
| `markets.py` | `/markets` | API | Market catalog, aliases, seeding |
| `imports.py` | — | API | CSV upload (Aposta odds, Oracle's Elixir) |
| `history.py` | — | API | Prediction/combo history, settlement |
| `lol_history.py` | `/lol-history` | API | LoL historical import, metrics, coverage |
| `dashboard.py` | `/dashboard` | API | Dashboard state, backtesting |
| `settings_integrations.py` | `/api/settings` | API | Credential management (auth, encryption, testing) |
| `matches.py` | `/matches` | API | Legacy CRUD for Match |
| `sports.py` | `/sports` | API | Legacy CRUD for Sport |
| `teams.py` | `/teams` | API | Legacy CRUD for Team |

`pages.py` is the only router returning HTML; all others are JSON REST endpoints.

## Service layer organization

~55 service modules in `backend/app/services/`:

### Core pipeline
- `aposta_sync.py` (19K) — Orchestrates odds import from Aposta.LA
- `aposta_snapshot.py` (13K) — Snapshot versioning, activation, expiration
- `aposta_snapshot_parser.py` — JSON/HTML parsing of Aposta.LA responses
- `event_identity.py` — Canonical event_key generation
- `event_matcher.py` — Matches odds to known sports events
- `event_lifecycle.py` — Derives local_event_state and produces diff for incremental refresh
- `refresh_queue.py` — Coalesced per-event queue with instance locking

### Historical & freshness
- `historical_ingestion.py` (55K — largest file) — Bounded historical backfill for active participants
- `fresh_football.py` (24K) — Fresh data via football-data.org + SofaScore browser fallback
- `event_history_window.py` — Strict per-event history window excluding anchor match
- `field_classification.py` — Classifies fields/markets for freshness marking
- `descriptive_stats.py` (25K) — Descriptive statistics read-model

### Recommendations
- `recommender/recommendation_service.py` (14K) — Top-level orchestration
- `recommender/probability_engine.py` — Implied probability from odds
- `recommender/ranking.py` — Four ranking modes
- `recommender/combo_builder.py` — Combo construction and deduplication

### Infrastructure
- `http_client.py` — Shared httpx client with pacing and caching
- `browser_fallback.py` — Browser rendering fallback
- `secret_provider.py` — Fernet-based credential encryption
- `dashboard_state.py`, `dashboard_refresh.py` — Dashboard state management
- `config_auth.py` — Settings UI authentication

See individual pages for deeper coverage: [data pipeline](../workflows/data-pipeline.md), [integrations](../integrations/overview.md).

## Source layer

External API connectors in `sources/football/` and `sources/lol/`:

| Source | Module | Rank | Auth |
|--------|--------|------|------|
| football-data.org v4 | `football/football_data_org.py` | 90 | `X-Auth-Token` |
| API-Football v3 | `football/api_football.py` | 88 | `x-apisports-key` |
| OpenLigaDB | `football/openligadb.py` | 70 | Public |
| TheSportsDB | `football/thesportsdb.py` | 60 | Free key `123` |
| Riot API | `lol/riot_api.py` | 80 | `X-Riot-Token` |
| Data Dragon | `lol/datadragon.py` | 75 | Public |

Each connector handles its own rate limiting, caching, and fallback logic.

## Configuration

All settings in `backend/app/config.py` via `pydantic-settings.BaseSettings`. Key groups:

- **App:** `app_name`, `app_env`, `app_timezone`, `database_url`, `log_level`
- **Football APIs:** `football_data_*`, `api_football_*`, `thesportsdb_*`, `openligadb_*`, `sofascore_worker_url`
- **LoL APIs:** `riot_*`, `datadragon_*`, `leaguepedia_*`, `lol_history_*`
- **Aposta.LA:** `aposta_sync_*`, `aposta_import_dir`, `aposta_archive_dir`
- **Recommender:** `recommender_default_mode`, `recommender_event_grace_minutes`

Secrets live in `.env` mounted as `/run/secrets/pirapire.env`. Integration credentials are additionally encrypted at rest via Fernet.
