# LolGameHistory

> God node · 17 connections · `backend/app/models_lol.py`

**Community:** [Oracle's Elixir Importer](Oracle%27s_Elixir_Importer.md)

## Connections by Relation

### calls
- _process_game() `EXTRACTED`

### contains
- models_lol.py `EXTRACTED`

### imports
- test_pages.py `EXTRACTED`
- lol_metrics_engine.py `EXTRACTED`
- lol_team_aliases.py `EXTRACTED`
- test_remote_oracles.py `EXTRACTED`
- oracles_elixir_importer.py `EXTRACTED`
- series_builder.py `EXTRACTED`

### indirect_call
- [_import_csv_file()](_import_csv_file%28%29.md) `INFERRED`
- [synchronize_known_aliases()](synchronize_known_aliases%28%29.md) `INFERRED`
- rebuild_series() `INFERRED`
- _series_games() `INFERRED`
- test_oracle_replacement_updates_and_removes_stale_games() `INFERRED`
- test_incremental_oracle_import_updates_present_games_without_pruning() `INFERRED`
- test_incremental_oracle_import_adds_only_new_games() `INFERRED`

### inherits
- SQLModel `EXTRACTED`

### uses
- _Response `INFERRED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*