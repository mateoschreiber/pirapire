# Source Map

Annotated guide to the `backend/app/` directory tree.

```
backend/
├── app/
│   ├── __init__.py               # Package marker (empty)
│   │
│   ├── main.py                   # FastAPI entrypoint. Lifespan: init_db() + synchronize_known_aliases(), 4 routers,
│   │                             #   static mount, /favicon.ico → favicon.svg
│   ├── config.py                 # Pydantic BaseSettings: all .env vars documented.
│   │                             #   New: lol_history_remote_max_mb, lol_history_remote_poll_minutes,
│   │                             #   team_logo_sync_interval_minutes. lol_history_interval_minutes → 60.
│   ├── database.py               # SQLModel engine + init_db() + get_session()
│   ├── migrations.py             # Idempotent ALTER TABLE ADD COLUMN for SQLite schema evolution.
│   │                             #   Also renames incompatible legacy tables (datasource→legacy_datasource,
│   │                             #   sourcerun→legacy_sourcerun) using PRAGMA column detection.
│   ├── worker_main.py            # APScheduler entrypoint. 8 recurring jobs (heartbeat, sync_schedule,
│   │                             #   sync_datadragon, import_odds, import_oracles,
│   │                             #   process_queued_oracle_uploads, precompute_stats,
│   │                             #   team_logo_sync).
│   │                             #   All long-running jobs skip while an Oracle import is active
│   │                             #   (_oracle_import_active). Web uploads are processed durably here
│   │                             #   instead of via BackgroundTasks.
│   ├── seed.py                   # Stale football-only seed (pre-refactor). Not used in LoL-only setup.
│   │                             #   Deleted from working tree but still tracked in git.
│   ├── models_lol.py             # All ORM models (~300 lines). Reference data, game history, series,
│   │                             #   match events, odds snapshots, stats cache, operational tracking.
│   └── schemas.py               # Pydantic response models: MatchResponse, UpcomingMatch,
│                                 #   UpcomingResponse, StatisticsResponse, OddsImportRequest
│
│   ├── routers/
│   │   ├── health.py             # GET /health → {"status": "ok"}
│   │   ├── pages.py              # HTML template routes: /, /lol/matches/{key}, /sources
│   │   ├── lol_api.py            # JSON API: /api/lol/matches/*. Competition classification,
│   │   │                         #   odds enrichment, statistics retrieval. Uses _utc_iso() to
│   │   │                         #   serialize SQLite naive datetimes with explicit +00:00 offset.
│   │   └── sources.py            # Source status, config GET/PUT, custom sources, alias sync,
│   │                             #   CSV upload, connectivity test, import/run history. Admin-auth.
│   │                             #   execute_import (POST /api/imports/execute) no longer uses
│   │                             #   BackgroundTasks — uploads are queued and processed durably
│   │                             #   by the worker's process_queued_oracle_uploads job.
│   │                             #   New: _leaguepedia_schedule_view() shows real scheduler state;
│   │                             #   _source_view() dispatches per-code views; auto_refresh and
│   │                             #   configuration_note for OE remote source config.
│   │
│   ├── services/
│   │   ├── http_client.py        # Shared httpx wrapper: timeout, retry, structured JSON
│   │   ├── series_builder.py     # Groups LolGameHistory → LolSeries. rebuild_series() entrypoint
│   │   ├── lol_metrics_engine.py # Team + player statistics from last 5 series. precompute_upcoming_stats().
│   │   │                         #   Player stats now report kills_per_map and deaths_per_map
│   │   │                         #   (per-map averages) instead of absolute kills/deaths totals.
│   │   │                         #   New: _recent_matchups() returns last 3 series summaries with
│   │   │                         #   opponent, score, kills/towers/inhibitors per side.
│   │   ├── lol_odds_importer.py  # CSV odds import: validation, team resolution, snapshots
│   │   ├── lol_team_aliases.py   # Team name normalization: NFKD alias resolution, upsert,
    │   │   │                             #   KNOWN_TEAM_ALIASES, EXHIBITION_TEAMS, synchronize_known_aliases()
│   │   ├── lol_league_catalog.py # League definitions, alias catalog, seed function
│   │   ├── team_logo_sync.py     # New. Downloads official team logos from lolesports.com
│   │   │                         #   tournament/league overview pages into static/team-logos/.
│   │   │                         #   Runs as a daily worker job (team_logo_sync_interval_minutes).
│   │   ├── lol_historical_importer.py  # (removed in refactor — merged into imports/)
│   │   │
│   │   ├── features/
│   │   │   └── lol_features.py   # Feature engineering for probability estimation.
│   │   │                         #   Not wired into current API. Legacy from betting pipeline.
│   │   │
│   │   ├── imports/
│   │   │   ├── oracles_elixir_importer.py  # Oracle's Elixir CSV import → game/team/player stats.
│   │   │   │                               #   _import_csv_file() now accepts prune_missing param.
│   │   │   └── remote_oracles_elixir.py    # New. Downloads OE CSV from remote URL (Google Drive
│   │   │                                   #   share links auto-converted). Validates headers,
│   │   │                                   #   streams to inbox, returns SHA-256 checksum.
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
│   │   ├── favicon.svg          # App favicon (SVG), served at /favicon.ico
│   │   ├── team-logos/          # Local cache of official team logos (populated by team_logo_sync)
│   │   ├── css/
│   │   │   └── styles.css       # Dashboard/match detail CSS + source-config forms. Sidebar layout, cards, tables.
│   │   └── js/
│   │       └── app.js           # Vanilla JS: dashboard rendering, match detail, data fetch.
│   │                           #   Uses es-PY locale, America/Asuncion timezone.
│   │
│   ├── templates/
│   │   ├── base.html           # Base template: sidebar nav, topbar with live clock, content slot,
│   │   │                       #   favicon link, cache-busted CSS/JS version query strings
│   │   ├── dashboard.html      # Competitive dashboard: filters, competition grid, match list
│   │   ├── match_detail.html   # Match detail: hero, odds, team stats, recent matchups card,
│   │   └── sources.html        # Source admin: status, file upload, run history, aliases tabs,
    │   │                             #   source config form, custom API registration.
    │   │                             #   Upload progress bar via XMLHttpRequest; durable queue
    │   │                             #   via POST /api/imports/execute → worker process.
    │   │                             #   New: configuration_note for OE, auto_refresh toggle,
    │   │                             #   managed_by badge for Leaguepedia schedule source.
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
    ├── test_health.py           # Health, favicon, source API + removed-domain tests
    ├── test_pages.py            # Page rendering, API endpoints, competition classifier,
    │   ├── test_pages.py        #   upload progress, per-map metrics, alias reconciliation,
    │   │                        #   source config + custom API tests
    ├── test_timezone.py         # Timezone conversion tests
    └── test_remote_oracles.py   # New. Remote CSV download, Google Drive URL conversion,
                                #   header validation, max-bytes enforcement
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

## Latest Additions (commits `56d9fe8` + uncommitted)

| File | What Changed |
|------|-------------|
| `services/imports/remote_oracles_elixir.py` | **New** — Downloads OE CSV from remote URL (Google Drive support) |
| `services/team_logo_sync.py` | **New** — Caches official team logos from lolesports.com |
| `services/lol_metrics_engine.py` | **Added** `_recent_matchups()` — last 3 series summaries per team |
| `routers/sources.py` | **Enhanced** — `_leaguepedia_schedule_view()`, `_source_view()`, auto_refresh for OE, configuration_note |
| `routers/lol_api.py` | **Added** `_utc_iso()` — naive SQLite datetime → explicit UTC ISO |
| `templates/base.html` | **Added** favicon link, cache-busted version query strings |
| `templates/match_detail.html` | **Added** `#recent-matchups` section after team stats |
| `templates/sources.html` | **Added** upload progress bar, `uploadImport()` JS, configuration_note, auto_refresh |
| `static/js/app.js` | **Updated** player kills/deaths to per-map averages; XHR upload with progress |
| `static/css/styles.css` | **Added** `.upload-progress` styles |
| `static/favicon.svg` | **New** — SVG favicon |
| `static/team-logos/` | **New** — Local team logo cache directory |
| `config.py` | **Extended** — `lol_history_remote_max_mb`, `lol_history_remote_poll_minutes`, `team_logo_sync_interval_minutes` |
| `main.py` | **Added** `/favicon.ico` route serving `favicon.svg` |
| `worker_main.py` | **Added** `_oracle_import_active()` guard; `job_process_queued_oracle_uploads()`; `job_team_logo_sync()`; removed `next_run_time=now` from sync jobs |
| `tests/test_health.py` | **Added** `test_favicon_is_served()`, richer sources API assertion |
| `tests/test_pages.py` | **Added** upload progress, `_utc_iso`, per-map kill/death assertions |
| `tests/test_remote_oracles.py` | **New** — Remote CSV download + validation tests |
| `migrations.py` | **Added** `_rename_incompatible_legacy_table()` — renames pre-LoL datasource/sourcerun tables |
| `backend/scripts/` | **New** — Admin/utility scripts directory |

### Removed from working tree

| File | Note |
|------|------|
| `backend/app/seed.py` | Pre-refactor football seed; no longer needed |
| `backend/app/services/features/` | Feature engineering (never wired into current API) |
| `backend/app/services/imports/csv_utils.py` | Stale CSV helpers referencing removed models |
| `backend/lol_metrics_engine.py` | Standalone script (superseded by app package version) |
| `backend/oracles_elixir_importer.py` | Standalone script (superseded by app package version) |
