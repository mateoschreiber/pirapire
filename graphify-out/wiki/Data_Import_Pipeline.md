# Data Import Pipeline

> 50 nodes

## Key Concepts

- **sources.py** (53 connections) — `backend/app/routers/sources.py`
- **Session** (25 connections)
- **SourceRun** (19 connections) — `backend/app/models_lol.py`
- **_source()** (15 connections) — `backend/app/routers/sources.py`
- **DataSource** (14 connections) — `backend/app/models_lol.py`
- **ImportBatch** (14 connections) — `backend/app/models_lol.py`
- **_execute_odds_import()** (14 connections) — `backend/app/routers/sources.py`
- **_process_import_batch()** (13 connections) — `backend/app/routers/sources.py`
- **_synchronize_history()** (11 connections) — `backend/app/routers/sources.py`
- **_now()** (8 connections) — `backend/app/routers/sources.py`
- **_leaguepedia_schedule_view()** (8 connections) — `backend/app/routers/sources.py`
- **save_source_configuration()** (8 connections) — `backend/app/routers/sources.py`
- **ValueError** (8 connections)
- **ImportError** (7 connections) — `backend/app/models_lol.py`
- **_config()** (7 connections) — `backend/app/routers/sources.py`
- **_source_view()** (7 connections) — `backend/app/routers/sources.py`
- **_queue_remote_oracle_sync()** (7 connections) — `backend/app/routers/sources.py`
- **execute_import()** (7 connections) — `backend/app/routers/sources.py`
- **test()** (6 connections) — `backend/app/routers/sources.py`
- **sync()** (6 connections) — `backend/app/routers/sources.py`
- **Path** (6 connections)
- **synchronize_sources()** (6 connections) — `backend/app/routers/sources.py`
- **_view()** (5 connections) — `backend/app/routers/sources.py`
- **_configuration_view()** (5 connections) — `backend/app/routers/sources.py`
- **sources()** (5 connections) — `backend/app/routers/sources.py`
- *... and 25 more nodes in this community*

## Relationships

- [Background Worker Jobs](Background_Worker_Jobs.md) (16 shared connections)
- [Core LoL Domain Models](Core_LoL_Domain_Models.md) (10 shared connections)
- [Match Events & Odds Models](Match_Events_%26_Odds_Models.md) (10 shared connections)
- [Oracle's Elixir Importer](Oracle%27s_Elixir_Importer.md) (7 shared connections)
- [Database & Migrations](Database_%26_Migrations.md) (6 shared connections)
- [Config, HTTP & Utils](Config%2C_HTTP_%26_Utils.md) (1 shared connections)

## Source Files

- `backend/app/models_lol.py`
- `backend/app/routers/sources.py`

## Audit Trail

- EXTRACTED: 323 (89%)
- INFERRED: 41 (11%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*