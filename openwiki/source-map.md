# Source Map

Annotated guide to the `backend/app/` directory tree.

```
backend/
├── app/
│   ├── __init__.py               # Package marker (empty)
│   │
│   ├── main.py                   # FastAPI entrypoint. Lifespan: init_db() + synchronize_known_aliases(), 4 routers, static mount
│   ├── config.py                 # Pydantic BaseSettings: all .env vars documented
│   ├── database.py               # SQLModel engine + init_db() + get_session()
│   ├── migrations.py             # Idempotent ALTER TABLE ADD COLUMN for SQLite schema evolution
│   ├── seed.py                   # Stale football-only seed (pre-refactor). Not used in LoL-only setup.
│   ├── models_lol.py             # All ORM models (~300 lines). Reference data, game history, series,
│   │                             #   match events, odds snapshots, stats cache, operational tracking.
│   └── schemas.py               # Pydantic response models: MatchResponse, UpcomingMatch,
│                                 #   UpcomingResponse, StatisticsResponse, OddsImportRequest
│
│   ├── routers/
│   │   ├── health.py             # GET /health → {"status": "ok"}
│   │   ├── pages.py              # HTML template routes: /, /lol/matches/{key}, /sources
│   │   ├── lol_api.py            # JSON API: /api/lol/matches/*. Competition classification,
│   │   │                         #   odds enrichment, statistics retrieval.
│   │   └── sources.py            # Source status, config GET/PUT, custom sources, alias sync,
│   │                             #   CSV upload, connectivity test, import/run history. Admin-auth.
│   │
│   ├── services/
│   │   ├── http_client.py        # Shared httpx wrapper: timeout, retry, structured JSON
│   │   ├── series_builder.py     # Groups LolGameHistory → LolSeries. rebuild_series() entrypoint
│   │   ├── lol_metrics_engine.py # Team + player statistics from last 5 series. precompute_upcoming_stats()
│   │   ├── lol_odds_importer.py  # CSV odds import: validation, team resolution, snapshots
│   │   ├── lol_team_aliases.py   # Team name normalization: NFKD alias resolution, upsert,
    │   │   │                             #   KNOWN_TEAM_ALIASES, EXHIBITION_TEAMS, synchronize_known_aliases()
│   │   ├── lol_league_catalog.py # League definitions, alias catalog, seed function
│   │   ├── lol_historical_importer.py  # (removed in refactor — merged into imports/)
│   │   │
│   │   ├── features/
│   │   │   └── lol_features.py   # Feature engineering for probability estimation.
│   │   │                         #   Not wired into current API. Legacy from betting pipeline.
│   │   │
│   │   ├── imports/
│   │   │   ├── oracles_elixir_importer.py  # Oracle's Elixir CSV import → game/team/player stats
│   │   │   └── csv_utils.py     # Shared CSV helpers (stale — references removed models)
│   │   │
│   │   └── sync/
│   │       └── lol_sync.py       # Leaguepedia schedule sync + Data Dragon champion sync
│   │
│   ├── sources/
│   │   ├── base.py              # SyncCounters dataclass, ISO datetime parser
│   │   └── lol/
│   │       └── datadragon.py    # RiotDataDragonClient: versions + champions fetch
│   │
│   ├── static/
│   │   ├── css/
│   │   │   └── styles.css       # Dashboard/match detail CSS + source-config forms. Sidebar layout, cards, tables.
│   │   └── js/
│   │       └── app.js           # Vanilla JS: dashboard rendering, match detail, data fetch.
│   │                           #   Uses es-PY locale, America/Asuncion timezone.
│   │
│   ├── templates/
│   │   ├── base.html           # Base template: sidebar nav, topbar with live clock, content slot
│   │   ├── dashboard.html      # Competitive dashboard: filters, competition grid, match list
│   │   ├── match_detail.html   # Match detail: hero, odds, team stats, player stats, coverage
│   │   └── sources.html        # Source admin: status, file upload, run history, aliases tabs,
    │   │                             #   source config form, custom API registration
│   │
│   └── utils/
│       └── datetime_utils.py   # Timezone helpers: UTC↔local conversion, format
│
├── lol_metrics_engine.py        # Standalone deduplication script (not wired; handles duplicate
│                                #   Oracle's Elixir CSV files by keeping first 5 maps per pair)
├── oracles_elixir_importer.py   # Standalone Oracle's Elixir dedup script
├── Dockerfile                   # Python 3.12-slim image
├── requirements.txt             # Python dependencies
├── pytest.ini                   # pytest config
└── tests/
    ├── conftest.py              # Temp SQLite DB init
    ├── test_health.py           # Health + source API + removed-domain tests
    ├── test_pages.py            # Page rendering, API endpoints, competition classifier,
    │   ├── test_pages.py            #   alias reconciliation + source config/custom API tests
    └── test_timezone.py         # Timezone conversion tests
```

## Key External Files

```
pirapire/
├── docker-compose.yml           # Two-container Compose (app + worker)
├── docker-compose.override.yml  # (example) Local development override
├── .env.example                 # Environment variable template
├── install.sh                   # Auto-install script (clone + docker compose)
├── README.md                    # Public README
├── migrate_phase1.sql           # SQL migration: drop legacy tables
├── data/                        # Volume mount for DB + imports
├── logs/                        # Volume mount for logs
└── docs/                        # Historical phase documentation (pre-refactor)
```

## Cross-Reference: Key Entry Points

| What you want to do | File to read first |
|--------------------|-------------------|
| Understand the data model | `models_lol.py` |
| Follow a web request | `main.py` → `routers/lol_api.py` or `routers/pages.py` |
| Understand stats computation | `services/lol_metrics_engine.py` |
| Understand CSV imports | `services/imports/oracles_elixir_importer.py`, `services/lol_odds_importer.py` |
| Add a new env var | `config.py` + `.env.example` + `docker-compose.yml` |
| Add a new data source | `sources/base.py` as pattern, `services/sync/lol_sync.py` as example |
| Debug a failed import | `routers/sources.py` for `/api/imports`, `/api/sources/runs` |
| Modify the dashboard UI | `templates/dashboard.html`, `static/js/app.js`, `static/css/styles.css` |
| Add a test | `tests/test_pages.py` as pattern (uses TestClient, real SQLite) |

## Latest Additions (commit `bb62c14`)

| File | What Changed |
|------|-------------|
| `services/series_builder.py` | **New** — Groups LolGameHistory → LolSeries. `rebuild_series()` entrypoint |
| `routers/sources.py` | **New** — Full source admin API: `/api/sources`, `/api/imports`, upload/preview |
| `templates/sources.html` | **New** — Tabbed admin UI (status, files, runs, aliases) |
| `migrations.py` | **New** — Idempotent ALTER TABLE ADD COLUMN via PRAGMA column detection |
| `models_lol.py` | Extended: LolSeries, LolTeam, LolPlayer, DataSource, SourceRun, ImportBatch, ImportError, WorkerHeartbeat |
| `services/lol_metrics_engine.py` | Refactored: series-based stats instead of raw games, strict Oracle's Elixir-only filter |
| `config.py` | Extended: `ADMIN_TOKEN`, HTTP timeout, history import settings |
| `database.py` | Updated: calls `migrations.upgrade()` after table creation |
