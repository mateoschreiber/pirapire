# Core LoL Domain Models

> 40 nodes

## Key Concepts

- **SQLModel** (38 connections)
- **models_lol.py** (36 connections) — `backend/app/models_lol.py`
- **lol_sync.py** (19 connections) — `backend/app/services/sync/lol_sync.py`
- **lol_league_catalog.py** (10 connections) — `backend/app/services/lol_league_catalog.py`
- **RiotDataDragonClient** (8 connections) — `backend/app/sources/lol/datadragon.py`
- **sync_leaguepedia_schedule()** (7 connections) — `backend/app/services/sync/lol_sync.py`
- **sync_datadragon()** (7 connections) — `backend/app/services/sync/lol_sync.py`
- **seed_catalog()** (6 connections) — `backend/app/services/lol_league_catalog.py`
- **_upsert_match_event()** (6 connections) — `backend/app/services/sync/lol_sync.py`
- **canonical_league()** (5 connections) — `backend/app/services/lol_league_catalog.py`
- **series_builder.py** (5 connections) — `backend/app/services/series_builder.py`
- **LolPatch** (4 connections) — `backend/app/models_lol.py`
- **LolChampion** (4 connections) — `backend/app/models_lol.py`
- **LolLeague** (4 connections) — `backend/app/models_lol.py`
- **LolLeagueAlias** (4 connections) — `backend/app/models_lol.py`
- **datadragon.py** (4 connections) — `backend/app/sources/lol/datadragon.py`
- **LolMatchStatisticsReadModel** (3 connections) — `backend/app/models_lol.py`
- **all_leagues()** (3 connections) — `backend/app/services/lol_league_catalog.py`
- **_upsert_patch()** (3 connections) — `backend/app/services/sync/lol_sync.py`
- **_upsert_champion()** (3 connections) — `backend/app/services/sync/lol_sync.py`
- **_fetch_all_pages()** (3 connections) — `backend/app/services/sync/lol_sync.py`
- **_now()** (2 connections) — `backend/app/models_lol.py`
- **datetime** (2 connections)
- **LolDataCoverage** (2 connections) — `backend/app/models_lol.py`
- **LolTeam** (2 connections) — `backend/app/models_lol.py`
- *... and 15 more nodes in this community*

## Relationships

- [Match Events & Odds Models](Match_Events_%26_Odds_Models.md) (21 shared connections)
- [Data Import Pipeline](Data_Import_Pipeline.md) (10 shared connections)
- [Oracle's Elixir Importer](Oracle%27s_Elixir_Importer.md) (10 shared connections)
- [Background Worker Jobs](Background_Worker_Jobs.md) (8 shared connections)
- [Match Statistics Engine](Match_Statistics_Engine.md) (5 shared connections)
- [Database & Migrations](Database_%26_Migrations.md) (4 shared connections)
- [Config, HTTP & Utils](Config%2C_HTTP_%26_Utils.md) (2 shared connections)

## Source Files

- `backend/app/models_lol.py`
- `backend/app/services/lol_league_catalog.py`
- `backend/app/services/series_builder.py`
- `backend/app/services/sync/lol_sync.py`
- `backend/app/sources/lol/datadragon.py`

## Audit Trail

- EXTRACTED: 211 (100%)
- INFERRED: 1 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*