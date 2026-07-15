# Architecture Overview

## Two-Container Deployment

Pirapire uses a single Docker image (`pirapire_app`) running as two services in Docker Compose:

```
pirapire/
├── docker-compose.yml
├── backend/
│   ├── Dockerfile          → image: pirapire_app
│   ├── requirements.txt
│   ├── pytest.ini
│   ├── app/                → Python application package
│   │   ├── main.py         → FastAPI entrypoint (uvicorn)
│   │   ├── worker_main.py  → APScheduler entrypoint
│   │   ├── config.py       → Pydantic Settings (.env)
│   │   ├── database.py     → SQLModel + SQLite engine
│   │   ├── migrations.py   → Idempotent SQLite column additions
│   │   └── ...
│   └── tests/
├── data/                    → Volume mount for SQLite + imports
├── logs/                    → Volume mount for log output
└── .env
```

**Source:** `/docker-compose.yml`, `/backend/Dockerfile`

## Web App (`app/main.py`)

FastAPI application with four router modules:

```
app.include_router(health.router)     # GET /health
app.include_router(lol_api.router)    # /api/lol/*
app.include_router(pages.router)      # HTML templates: /, /lol/matches/{key}, /sources
app.include_router(sources.router)    # /api/sources, /api/imports
app.mount("/static", ...)             # CSS + JS
```

- **Lifespan handler** calls `init_db()` on startup (creates tables, runs migrations)
- **Templates** rendered via Jinja2 from `app/templates/`
- **Static assets** served from `app/static/`

## Background Worker (`app/worker_main.py`)

APScheduler `BackgroundScheduler` with five recurring jobs:

| Job | Interval | Description |
|-----|----------|-------------|
| `heartbeat` | 1 min | Writes `WorkerHeartbeat` row |
| `sync_schedule` | 30 min | Leaguepedia schedule sync |
| `sync_datadragon` | 1440 min | Data Dragon champion/version sync |
| `import_odds` | 5 min | Polls odds CSV inbox |
| `import_oracles` | 30 min | Polls Oracle's Elixir CSV inbox |

Additionally, `job_precompute_stats()` is defined but not scheduled by default (configure as needed).

## Database Layer

- **SQLModel** ORM over SQLite (configurable via `DATABASE_URL`)
- `connect_args = {"check_same_thread": False}` for SQLite concurrent access
- `init_db()`: creates all tables from SQLModel metadata, then runs `migrations.upgrade()`
- **Migrations** (`app/migrations.py`): idempotent `ALTER TABLE ADD COLUMN` for schema evolution without Alembic
- **Session management:** `get_session()` FastAPI dependency yields `Session(engine)`

## Database Models

All models in `app/models_lol.py` (~300 lines). Key model groups:

**Reference data:**
- `LolPatch`, `LolChampion`, `LolLeague`, `LolLeagueAlias` — Static LoL metadata
- `LolTeamAlias` — Team name normalization table
- `LolTeam`, `LolPlayer`, `LolTeamExternalIdentity`, `LolPlayerExternalIdentity` — Stable identity records

**Historical game data:**
- `LolGameHistory`, `LolTeamGameStat`, `LolPlayerGameStat` — Oracle's Elixir competitive match data
- `LolSeries` — Groups individual games into best-of series
- `LolDataCoverage` — Per-league/year import tracking

**Match events & odds:**
- `LolMatchEvent` — Upcoming/finished professional series from Leaguepedia
- `LolOddsSnapshot`, `LolTeamOdd` — Immutable odds captures per match

**Cached statistics:**
- `LolMatchStatisticsReadModel` — Materialised pre-match statistics payload

**Operational:**
- `DataSource`, `SourceRun` — Source status tracking
- `ImportBatch`, `ImportError` — CSV import tracking
- `WorkerHeartbeat` — Worker health monitoring

## Service Layer Detail

### Source Management & Admin API (`/backend/app/routers/sources.py`)
The sources router (23279 bytes — largest router) provides:
- `GET /api/sources` — List all data sources with status
- `GET /api/sources/detail/{code}` — Source detail
- `POST /api/sources/{code}/test` — Test connectivity (admin token required)
- `POST /api/sources/{code}/sync` — Trigger sync (stub — returns "Adapter sync is not configured")
- `GET /api/sources/runs` — Last 100 source run records
- `GET /api/sources/runs/{run_id}` — Run detail
- `GET /api/imports` — Last 100 import batches
- `GET /api/imports/{batch_id}` — Batch detail with latest error
- `GET /api/imports/{batch_id}/errors` — Batch errors
- `POST /api/sources/oracles/upload` — Upload CSV/ZIP file for Oracle's Elixir (100 MB limit, SHA-256 dedup)
- `POST /api/imports/preview` — Preview upload rows without persisting
- `POST /api/imports/save` — Validate and commit batch

All write operations require `X-Admin-Token` header matching `settings.admin_token`.

### Timezone Handling (`/backend/app/utils/datetime_utils.py`)
- All times stored as UTC in SQLite
- Display conversion to `APP_TIMEZONE` (default: `America/Asuncion`)
- `format_local()` returns localized string; `offset_str()` returns offset like `-03:00`

## Developer Change Guidance

When modifying this codebase, watch for:

1. **SQLite concurrent access:** The worker and web app share the same SQLite file. `check_same_thread=False` is critical. No WAL mode is configured currently — be aware of potential `database is locked` under heavy concurrent writes.
2. **APScheduler in-process:** The worker uses `BackgroundScheduler` without an external broker. It is not distributed and restarts on container restart.
3. **Functional service pattern:** Services are modules of free functions, not classes. All take `Session` as first argument.
4. **No Alembic:** Schema migrations are done via `PRAGMA table_info` + `ALTER TABLE ADD COLUMN` in `migrations.py`. New models need both a SQLModel class and potentially a migration entry.
5. **Frontend is vanilla JS:** No framework. Template rendering is server-side Jinja2 with JavaScript fetching JSON from `/api/lol/matches/*` endpoints.
6. **Stale seed.py:** `/backend/app/seed.py` references deleted football models and will fail if called. It is a pre-Phase-1 artifact.
7. **Duplicate standalone scripts:** `/backend/lol_metrics_engine.py` and `/backend/oracles_elixir_importer.py` exist at the backend root — these are older versions superseded by the app package versions. Do not import them.

## Service Layer Detail

### `lol_metrics_engine.py`
Core statistics engine. Computes team and player metrics from the last 5 complete Oracle's Elixir series per team. Key functions:
- `_recent_series()` — Fetches last 5 complete series from LolSeries (Oracle's Elixir only)
- `_team_payload()` — Computes percentage metrics (towers, inhibitors, kills, deaths, dragons, barons, gold), absolute averages, and coverage labels
- `_players()` — Computes per-player metrics (kills %, deaths %, gold %, CS per map, solo kills)
- `precompute_upcoming_stats()` — Iterates all upcoming LolMatchEvents, computes stats, writes LolMatchStatisticsReadModel

### `series_builder.py`
Groups LolGameHistory records into LolSeries. `rebuild_series()`:
1. Buckets games by (league, date[:10], sorted_team_pair)
2. Creates series with scores, best_of (1/3/5), game_ids_json
3. Links games to series via series_id FK
4. Wipes and rebuilds all series atomically

### `lol_team_aliases.py`
Team name normalization. `canonical_team()` uses a multi-step resolution:
1. Exact alias match → return canonical
2. NFKD normalized match (with noise word removal: esports, gaming, team, club, lol)
3. Optional league-scoped alias lookup

### `lol_league_catalog.py`
Defines 9 active tier-1 leagues (LCK, LPL, LEC, LCS, CBLOL, LCP, MSI, WORLDS, FIRST_STAND) and 8 legacy leagues (LTA, LLA, PCS, VCS, LJL, LCO, TCL, LCL). `canonical_league()` maps any input string to a canonical slug.

## Key Git History

### Phase 1 Refactor (commit `b8e1b04`)
Pirapire was originally a multi-sport analytics platform (football + LoL) with betting integrations (Aposta, Kambi). The Phase 1 refactor stripped all non-LoL code:

- **Removed:** ~40 service files, 15+ routers, football models, betting models, browser worker
- **Kept:** All LoL models, Oracle's Elixir importer, Data Dragon source, Leaguepedia sync
- **Rewired:** `lol_api.py`, `lol_metrics_engine.py`, `pages.py` as new single-purpose routers
- **New:** `series_builder.py`, `migrations.py`, `sources.py` router, `worker_main.py`

### Latest Commit (bb62c14)
- **Series builder** (`services/series_builder.py`) — New service that groups LolGameHistory records into LolSeries
- **Sources admin API** (`routers/sources.py`) — New router exposing `/api/sources`, `/api/imports`, `/api/sources/oracles/upload`
- **Migrations** (`app/migrations.py`) — Idempotent SQLite schema evolution with PRAGMA-based column detection
- **Metrics engine refinements** — Series-based lookup (instead of game-based), strict Oracle's Elixir filter, updated precomputation
- **Sources HTML page** (`templates/sources.html`) — Tabbed admin UI with status, file upload, run history, aliases views

### Subsequent commits:
- **`c934c55`:** On-demand stats, `LolSeries` model, team aliases, timezone fix
- **`a741fa1`:** Switched Leaguepedia to `MatchSchedule` table, added odds importer
- **`d89b75b`:** Corrected duplicate service files left at root level
- **`bb62c14`:** Sources admin UI + API, migrations module, series_builder, refined metrics

The migration SQL script (`migrate_phase1.sql`) drops all legacy tables and runs integrity checks.
