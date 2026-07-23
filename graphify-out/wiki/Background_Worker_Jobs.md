# Background Worker Jobs

> 22 nodes

## Key Concepts

- **worker_main.py** (33 connections) — `backend/app/worker_main.py`
- **rebuild_series()** (13 connections) — `backend/app/services/series_builder.py`
- **_oracle_import_active()** (13 connections) — `backend/app/worker_main.py`
- **_session()** (12 connections) — `backend/app/worker_main.py`
- **_process_remote_oracle_run()** (11 connections) — `backend/app/worker_main.py`
- **job_sync_remote_oracles()** (7 connections) — `backend/app/worker_main.py`
- **job_process_queued_oracle_uploads()** (6 connections) — `backend/app/worker_main.py`
- **job_process_queued_remote_oracles()** (6 connections) — `backend/app/worker_main.py`
- **_remote_oracle_config()** (5 connections) — `backend/app/worker_main.py`
- **WorkerHeartbeat** (4 connections) — `backend/app/models_lol.py`
- **job_sync_schedule()** (4 connections) — `backend/app/worker_main.py`
- **job_sync_datadragon()** (4 connections) — `backend/app/worker_main.py`
- **job_import_odds()** (4 connections) — `backend/app/worker_main.py`
- **job_import_oracles()** (4 connections) — `backend/app/worker_main.py`
- **_finish_remote_run()** (4 connections) — `backend/app/worker_main.py`
- **job_heartbeat()** (4 connections) — `backend/app/worker_main.py`
- **job_precompute_stats()** (4 connections) — `backend/app/worker_main.py`
- **Session** (1 connections)
- **Process UI uploads durably from the worker instead of the web process.** (1 connections) — `backend/app/worker_main.py`
- **Download the configured CSV and update or add the games it contains.** (1 connections) — `backend/app/worker_main.py`
- **Run pending manual requests, or the scheduled refresh of the configured remote C** (1 connections) — `backend/app/worker_main.py`
- **Pick up a user-requested remote refresh without waiting for the scheduled interv** (1 connections) — `backend/app/worker_main.py`

## Relationships

- [Data Import Pipeline](Data_Import_Pipeline.md) (16 shared connections)
- [Oracle's Elixir Importer](Oracle%27s_Elixir_Importer.md) (9 shared connections)
- [Core LoL Domain Models](Core_LoL_Domain_Models.md) (8 shared connections)
- [Match Events & Odds Models](Match_Events_%26_Odds_Models.md) (4 shared connections)
- [Match Statistics Engine](Match_Statistics_Engine.md) (3 shared connections)
- [Database & Migrations](Database_%26_Migrations.md) (2 shared connections)
- [Team Logo Sync Service](Team_Logo_Sync_Service.md) (2 shared connections)
- [Config, HTTP & Utils](Config%2C_HTTP_%26_Utils.md) (1 shared connections)

## Source Files

- `backend/app/models_lol.py`
- `backend/app/services/series_builder.py`
- `backend/app/worker_main.py`

## Audit Trail

- EXTRACTED: 135 (94%)
- INFERRED: 8 (6%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*