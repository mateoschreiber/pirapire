# SourceRun

> God node · 19 connections · `backend/app/models_lol.py`

**Community:** [Data Import Pipeline](Data_Import_Pipeline.md)

## Connections by Relation

### calls
- _execute_odds_import() `EXTRACTED`
- _process_import_batch() `EXTRACTED`
- job_sync_remote_oracles() `EXTRACTED`
- sync() `EXTRACTED`
- synchronize_sources() `EXTRACTED`
- test() `EXTRACTED`

### contains
- models_lol.py `EXTRACTED`

### imports
- sources.py `EXTRACTED`
- worker_main.py `EXTRACTED`
- migrations.py `EXTRACTED`

### indirect_call
- _oracle_import_active() `INFERRED`
- _synchronize_history() `INFERRED`
- _process_remote_oracle_run() `INFERRED`
- job_process_queued_remote_oracles() `INFERRED`
- _finish_remote_run() `INFERRED`
- run_status() `INFERRED`
- runs() `INFERRED`

### inherits
- SQLModel `EXTRACTED`

### references
- _queue_remote_oracle_sync() `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*