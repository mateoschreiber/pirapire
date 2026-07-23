# LolMatchEvent

> God node · 23 connections · `backend/app/models_lol.py`

**Community:** [Match Events & Odds Models](Match_Events_%26_Odds_Models.md)

## Connections by Relation

### calls
- _upsert_match_event() `EXTRACTED`
- test_known_aliases_reconcile_renamed_teams() `EXTRACTED`
- test_manual_odds_upload_and_match_response() `EXTRACTED`

### contains
- models_lol.py `EXTRACTED`

### imports
- sources.py `EXTRACTED`
- test_pages.py `EXTRACTED`
- lol_api.py `EXTRACTED`
- lol_metrics_engine.py `EXTRACTED`
- lol_sync.py `EXTRACTED`
- lol_team_aliases.py `EXTRACTED`
- lol_odds_importer.py `EXTRACTED`

### indirect_call
- [synchronize_known_aliases()](synchronize_known_aliases%28%29.md) `INFERRED`
- import_odds_csv() `INFERRED`
- _leaguepedia_schedule_view() `INFERRED`
- compute_match_statistics() `INFERRED`
- upcoming_matches() `INFERRED`
- sync_leaguepedia_schedule() `INFERRED`
- get_match() `INFERRED`

### inherits
- SQLModel `EXTRACTED`

### rationale_for
- Upcoming or finished professional LoL series. `EXTRACTED`

### references
- _match_view() `EXTRACTED`
- _odds_for_match() `EXTRACTED`
- _competition_summary() `EXTRACTED`

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*