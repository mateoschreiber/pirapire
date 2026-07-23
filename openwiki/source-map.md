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
│   ├── worker_main.py            # APScheduler entrypoint. 10 recurring jobs (heartbeat, sync_schedule,
│   │                             #   sync_datadragon, sync_team_logos, import_odds, import_oracles,
│   │                             #   process_queued_oracle_uploads, sync_remote_oracles,
│   │                             #   process_queued_remote_oracles, precompute_stats).
│   │                             #   All long-running jobs skip while an Oracle import is active
│   │                             #   (_oracle_import_active). Web uploads are processed durably here
│   │                             #   instead of via BackgroundTasks.
│   │                             #   Remote Oracle sync checks SHA-256 before re-import.
│   │                             #   process_queued_remote_oracles picks up user-requested sync.
│   ├── seed.py                   # Stale football-only seed (pre-refactor). Not used in LoL-only setup.
│   │                             #   Deleted from working tree but still tracked in git.
│   ├── models_lol.py             # All ORM models (~300 lines). Reference data, game history, series,
│   │                             #   match events, odds snapshots, stats cache, operational tracking.
│   │                             #   LolMatchStatisticsReadModel.payload_json/coverage_json are
│   │                             #   Optional[dict] (JSON columns), not strings.
│   └── schemas.py               # Pydantic response models: MatchResponse, UpcomingMatch,
│                                 #   UpcomingResponse, StatisticsResponse, OddsImportRequest
│
│   ├── routers/
│   │   ├── health.py             # GET /health → {"status": "ok"}
│   │   ├── pages.py              # HTML template routes: /, /lol/matches/{key}, /sources
│   │   ├── lol_api.py            # JSON API: /api/lol/matches/*. Competition classification,
│   │   │                         #   odds enrichment, statistics retrieval. Uses _utc_iso() to
│   │   │                         #   serialize SQLite naive datetimes with explicit +00:00 offset.
│   │   │                         #   /statistics endpoint now serves from LolMatchStatisticsReadModel cache.
│   │   │                         #   /upcoming batch-loads cache + odds for all matches (2N → 2 queries).
│   │   │                         #   KESPA added to COMPETITIONS (11 total).
│   │   │                         #   _match_view() accepts optional estimated_market + odds params.
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
│   │   ├── lol_metrics_engine.py # Team + player statistics from last 5 series. precompute_upcoming_stats()
│   │   │                         #   now caches to LolMatchStatisticsReadModel. New caching layer:
│   │   │                         #   cached_match_statistics(), store_match_statistics(),
│   │   │                         #   invalidate_statistics_cache(), cached_statistics_from_record().
│   │   │                         #   Player stats now report kills_per_map and deaths_per_map
│   │   │                         #   (per-map averages) instead of absolute kills/deaths totals.
│   │   │                         #   New: _recent_matchups() returns last 3 series summaries with
│   │   │                         #   opponent, score, kills/towers/inhibitors per side.
│   │   ├── lol_odds_importer.py  # CSV odds import: validation, team resolution, snapshots
│   │   ├── lol_team_aliases.py   # Team name normalization: NFKD alias resolution, upsert,
    │   │   │                             #   KNOWN_TEAM_ALIASES, EXHIBITION_TEAMS, synchronize_known_aliases()
│   │   ├── lol_league_catalog.py # League definitions, alias catalog, seed function
│   │   ├── team_logo_sync.py     # Downloads official team logos from lolesports.com pages
│   │   │                         #   + DISPLAY_ALIASES (17 provider->official mappings), OFFICIAL_TEAM_ASSETS
│   │   │                         #   (direct-url fallback for cnb-legends, mibr). Runs daily worker job.
│   │   ├── lol_historical_importer.py  # (removed in refactor — merged into imports/)
│   │   │
│   │   ├── imports/
│   │   │   ├── oracles_elixir_importer.py  # Oracle's Elixir CSV import → game/team/player stats.
│   │   │   │                               #   _import_csv_file() now accepts prune_missing param.
│   │   │   └── remote_oracles_elixir.py    # Downloads OE CSV from remote URL (Google Drive
│   │   │                                   #   share links auto-converted). Validates headers,
│   │   │                                   #   streams to inbox, returns SHA-256 checksum.
│   │   │                                   #   Supports quota-exceeded detection and size limits.
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
│   │       └── app.js           # Vanilla JS: dashboard + match detail rendering, preview odds
│   │                           #   rendered server-side in match.estimated_market (no async fetch).
│   │                           #   Uses es-PY locale, America/Asuncion timezone.
│   │                           #   Uses es-PY locale, America/Asuncion timezone.
│   │
│   ├── templates/
│   │   ├── base.html           # Base template: sidebar nav, topbar with live clock, content slot,
│   │   │                       #   favicon link, cache-busted CSS/JS version query strings
│   │   ├── dashboard.html      # Competitive dashboard: collapsible disclosure sections, filters, grid
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
    │   │                        #   source config + custom API tests. 11 competitions (KESPA added).
    ├── test_statistics_cache.py # New. Cache precompute persist + reuse, API serves from cache
    ├── test_timezone.py         # Timezone conversion tests
    └── test_remote_oracles.py   # New. Remote CSV download, Google Drive URL conversion,
                                #   header validation, max-bytes enforcement
```

## Key External Files

```
pirapire/
├── docker-compose.yml           # Two-container Compose (app + worker); mounts team-logos volume
├── docker-compose.override.yml  # (example) Local development override
├── .env.example                 # Environment variable template
├── install.sh                   # Auto-install script (clone + docker compose)
├── README.md                    # Public README
├── data/                        # Volume mount for DB + imports
├── logs/                        # Volume mount for logs
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

## Latest Additions (commits `56d9fe8`, uncommitted caching + KESPA)

| File | What Changed |
|------|-------------|
| `services/lol_metrics_engine.py` | **Added** `_recent_matchups()` — last 3 individual maps per team; **added statistics caching layer** — `cached_match_statistics()`, `store_match_statistics()`, `invalidate_statistics_cache()`, `cached_statistics_from_record()`, `_cache_fingerprint()`. `precompute_upcoming_stats()` now persists to `LolMatchStatisticsReadModel` |
| `routers/lol_api.py` | **Added** `_utc_iso()` — naive SQLite datetime → explicit UTC ISO; **batch odds loading** via `_current_odds_by_match()` (2 queries vs 2N); **KESPA** added to COMPETITIONS (11 total); `/statistics` endpoint serves from cache; `/upcoming` loads cached stats inline |
| `models_lol.py` | **Changed** `LolMatchStatisticsReadModel.payload_json`/`coverage_json` from `Optional[str]` to `Optional[dict]` |
| `migrations.py` | **Added** performance indexes: `ix_lolmatchevent_status_start`, `ix_lolseries_team_a_stats`, `ix_lolseries_team_b_stats` |
| `services/series_builder.py` | **Added** `invalidate_statistics_cache()` call after rebuild |
| `services/sync/lol_sync.py` | **Added** early-exit skip detection (no-op if match unchanged); `invalidate_statistics_cache()` after schedule sync |
| `services/imports/oracles_elixir_importer.py` | **Added** `rebuild_series()` call after inbox import |
| `worker_main.py` | **Changed** `precompute_stats` job now uses `next_run_time=now` (runs immediately on worker start) |
| `static/js/app.js` | **Removed** `loadPreviewOdds()`, `previewOddsCache`, concurrent fetcher; preview odds now rendered server-side from `match.estimated_market`; added `pending` status handling for statistics endpoint |
| `tests/test_statistics_cache.py` | **New** — Cache precompute persist + reuse, API serves from cache without recomputing |
| `services/imports/remote_oracles_elixir.py` | **New** — Downloads OE CSV from remote URL (Google Drive support) |
| `services/team_logo_sync.py` | **New** — Caches official team logos from lolesports.com. DISPLAY_ALIASES maps provider names to cached assets; OFFICIAL_TEAM_ASSETS with direct-url fallback for cnb-legends, mibr |
| `routers/sources.py` | **Enhanced** — `_leaguepedia_schedule_view()`, `_source_view()`, auto_refresh for OE, configuration_note |
| `static/css/styles.css` | **Added** `.upload-progress` styles |
| `static/favicon.svg` | **New** — SVG favicon |
| `static/team-logos/` | **New** — Local team logo cache directory |
| `config.py` | **Extended** — `lol_history_remote_max_mb`, `lol_history_remote_poll_minutes`, `team_logo_sync_interval_minutes` |
| `main.py` | **Added** `/favicon.ico` route serving `favicon.svg` |
| `worker_main.py` | **Added** `_oracle_import_active()` guard; `job_process_queued_oracle_uploads()`; `job_team_logo_sync()`; removed `next_run_time=now` from sync jobs |
| `tests/test_health.py` | **Added** `test_favicon_is_served()`, richer sources API assertion |
| `tests/test_pages.py` | **Added** upload progress, `_utc_iso`, per-map kill/death assertions |
| `tests/test_remote_oracles.py` | **New** — Remote CSV download + validation tests |
| `docker-compose.yml` | **Updated** — mounts team-logos volume for both containers |
| `migrations.py` | **Added** `_rename_incompatible_legacy_table()` — renames pre-LoL datasource/sourcerun tables |
| `backend/scripts/` | **New** — Admin/utility scripts directory |

### Removed from working tree

| File | Note |
|------|------|
| `backend/app/seed.py` | Pre-refactor football seed; no longer needed |
| `backend/app/services/features/` | Feature engineering directory (deleted from working tree) |
| `backend/app/services/imports/csv_utils.py` | Stale CSV helpers referencing removed models |
| `backend/lol_metrics_engine.py` | Standalone script (superseded by app package version) |
| `backend/oracles_elixir_importer.py` | Standalone script (superseded by app package version) |
| `docs/` | Historical phase documentation (pre-refactor) |
| `migrate_phase1.sql` | One-time migration script (already run) |
