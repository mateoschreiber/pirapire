# Oracle's Elixir Importer

> 40 nodes

## Key Concepts

- **_import_csv_file()** (22 connections) — `backend/app/services/imports/oracles_elixir_importer.py`
- **LolGameHistory** (17 connections) — `backend/app/models_lol.py`
- **LolTeamGameStat** (15 connections) — `backend/app/models_lol.py`
- **test_remote_oracles.py** (15 connections) — `backend/tests/test_remote_oracles.py`
- **download_remote_csv()** (12 connections) — `backend/app/services/imports/remote_oracles_elixir.py`
- **_Response** (12 connections) — `backend/tests/test_remote_oracles.py`
- **LolPlayerGameStat** (11 connections) — `backend/app/models_lol.py`
- **oracles_elixir_importer.py** (11 connections) — `backend/app/services/imports/oracles_elixir_importer.py`
- **remote_oracles_elixir.py** (9 connections) — `backend/app/services/imports/remote_oracles_elixir.py`
- **RemoteCsvError** (9 connections) — `backend/app/services/imports/remote_oracles_elixir.py`
- **_process_game()** (8 connections) — `backend/app/services/imports/oracles_elixir_importer.py`
- **import_remote_oracles_csv()** (7 connections) — `backend/app/services/imports/remote_oracles_elixir.py`
- **google_drive_download_url()** (6 connections) — `backend/app/services/imports/remote_oracles_elixir.py`
- **import_oracles_inbox()** (5 connections) — `backend/app/services/imports/oracles_elixir_importer.py`
- **test_oracle_replacement_updates_and_removes_stale_games()** (5 connections) — `backend/tests/test_pages.py`
- **_validate_csv()** (4 connections) — `backend/app/services/imports/remote_oracles_elixir.py`
- **test_remote_csv_reports_google_drive_quota()** (4 connections) — `backend/tests/test_remote_oracles.py`
- **test_incremental_oracle_import_updates_present_games_without_pruning()** (4 connections) — `backend/tests/test_remote_oracles.py`
- **_int()** (3 connections) — `backend/app/services/imports/oracles_elixir_importer.py`
- **_bool()** (3 connections) — `backend/app/services/imports/oracles_elixir_importer.py`
- **Session** (3 connections)
- **Path** (3 connections)
- **test_remote_csv_is_downloaded_and_validated()** (3 connections) — `backend/tests/test_remote_oracles.py`
- **test_incremental_oracle_import_adds_only_new_games()** (3 connections) — `backend/tests/test_remote_oracles.py`
- **_normalized_row()** (2 connections) — `backend/app/services/imports/oracles_elixir_importer.py`
- *... and 15 more nodes in this community*

## Relationships

- [Match Events & Odds Models](Match_Events_%26_Odds_Models.md) (11 shared connections)
- [Core LoL Domain Models](Core_LoL_Domain_Models.md) (10 shared connections)
- [Background Worker Jobs](Background_Worker_Jobs.md) (9 shared connections)
- [Match Statistics Engine](Match_Statistics_Engine.md) (7 shared connections)
- [Data Import Pipeline](Data_Import_Pipeline.md) (7 shared connections)
- [Config, HTTP & Utils](Config%2C_HTTP_%26_Utils.md) (1 shared connections)

## Source Files

- `backend/app/models_lol.py`
- `backend/app/services/imports/oracles_elixir_importer.py`
- `backend/app/services/imports/remote_oracles_elixir.py`
- `backend/tests/test_pages.py`
- `backend/tests/test_remote_oracles.py`

## Audit Trail

- EXTRACTED: 178 (84%)
- INFERRED: 35 (16%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*