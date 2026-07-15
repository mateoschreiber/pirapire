# Pirapire — LoL Esports Analytics Platform

**Pirapire** is a Python-based analytics platform for professional League of Legends matches. It displays upcoming matches with odds and computes competitive statistics from historical match data (Oracle's Elixir CSV, Leaguepedia schedule).

## Quick Start

```bash
git clone https://github.com/mateoschreiber/pirapire.git
cd pirapire
cp .env.example .env
# Edit .env if needed (see operations/runbook.md for env reference)
docker compose up -d --build
```

Open **http://localhost:8090**.

**Requirements:** Docker 24+, Docker Compose v2, 2 GB RAM, 1 GB disk.

## At a Glance

| Layer | Technology | Key Path |
|-------|-----------|----------|
| Web framework | FastAPI | `/backend/app/main.py` |
| Database | SQLite via SQLModel / SQLAlchemy | `/backend/app/database.py` |
| Templates | Jinja2 (server-rendered) | `/backend/app/templates/` |
| Frontend | Vanilla JS + CSS | `/backend/app/static/` |
| Background worker | APScheduler | `/backend/app/worker_main.py` |
| Runtime | Docker (app + worker containers) | `/docker-compose.yml` |

## What This Wiki Covers

| Page | Description |
|------|-------------|
| [Architecture Overview](architecture/overview.md) | Two-container design, routing tree, database models, service layer, scheduler |
| [LoL Domain & Metrics](domain/lol-metrics.md) | Match events, series, game history, statistics engine, competition classification, team aliases |
| [Data Pipeline Workflows](workflows/data-pipeline.md) | Leaguepedia sync, OE import, odds import, series building, stats precomputation |
| [Integrations](integrations/overview.md) | External data sources: Leaguepedia, Data Dragon, Oracle's Elixir CSV |
| [Operations / Runbook](operations/runbook.md) | Deployment, env vars, imports admin, health check, troubleshooting |
| [Testing](testing/overview.md) | Test structure, conftest setup, key test patterns |
| [Source Map](source-map.md) | Annotated directory tree with file-by-file descriptions |

## Key Concepts

- **Series** — A best-of-N match between two LoL teams, composed of individual maps (games). The `LolSeries` model groups `LolGameHistory` records by league + date + team pair.
- **Statistics Engine** — Computes team and player metrics from the last 5 completed series per team (strictly before match kickoff). Produces percentages for towers, inhibitors, kills, deaths, dragons, barons, gold plus average map/series duration.
- **Coverage Labels** — Metrics are tagged `complete`, `partial`, or `unavailable` based on how many recent series had usable data.
- **Team Aliases** — Normalizes team names across sources (Leaguepedia, Oracle's Elixir manual CSV) using a flexible alias table with NFKD normalization.
- **Competition Classification** — Matches are classified into standard league codes (`LCK`, `LPL`, `LEC`, `LTA`, `LCP`, `WORLDS`, `MSI`, `FIRST_STAND`, `EWC`).

## Data Flow

```
Leaguepedia Cargo API  ──►  LolMatchEvent (schedule)
Oracle's Elixir CSV    ──►  LolGameHistory + LolTeamGameStat + LolPlayerGameStat
Manual odds CSV        ──►  LolOddsSnapshot + LolTeamOdd
Data Dragon API         ──►  LolPatch + LolChampion

           │
           ▼
    Series Builder ──► LolSeries (group games)
           │
           ▼
    Metrics Engine ──► LolMatchStatisticsReadModel (cached stats)
           │
           ▼
    Dashboard / Match Detail pages
```

## Backlog

The following areas are not yet documented in this wiki:

| Area | Source Anchor | Reason |
|------|--------------|--------|
| Legacy docs in /docs/ | `/docs/` | Historical phase docs (4a–4d2) from pre-refactor; largely obsolete for current LoL-only codebase |
| Phase 1 migration SQL | `/migrate_phase1.sql` | One-time cleanup script for dropping legacy tables |
| seed.py | `/backend/app/seed.py` | Stale football-only seed from pre-refactor era; not relevant to LoL-only setup |
