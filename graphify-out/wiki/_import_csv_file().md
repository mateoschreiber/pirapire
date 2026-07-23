# _import_csv_file()

> God node · 22 connections · `backend/app/services/imports/oracles_elixir_importer.py`

**Community:** [Oracle's Elixir Importer](Oracle%27s_Elixir_Importer.md)

## Connections by Relation

### calls
- _process_import_batch() `EXTRACTED`
- _synchronize_history() `EXTRACTED`
- _process_remote_oracle_run() `EXTRACTED`
- _process_game() `EXTRACTED`
- ValueError `INFERRED`
- import_remote_oracles_csv() `EXTRACTED`
- import_oracles_inbox() `EXTRACTED`
- test_oracle_replacement_updates_and_removes_stale_games() `EXTRACTED`
- test_incremental_oracle_import_updates_present_games_without_pruning() `EXTRACTED`
- test_incremental_oracle_import_adds_only_new_games() `EXTRACTED`
- _normalized_row() `EXTRACTED`

### contains
- oracles_elixir_importer.py `EXTRACTED`

### imports
- sources.py `EXTRACTED`
- worker_main.py `EXTRACTED`
- test_pages.py `EXTRACTED`
- test_remote_oracles.py `EXTRACTED`
- remote_oracles_elixir.py `EXTRACTED`

### indirect_call
- [LolGameHistory](LolGameHistory.md) `INFERRED`
- [LolTeamGameStat](LolTeamGameStat.md) `INFERRED`
- LolPlayerGameStat `INFERRED`

### rationale_for
- Import an OE CSV, optionally updating existing games and pruning missing maps. `EXTRACTED`

### references
- Session `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*