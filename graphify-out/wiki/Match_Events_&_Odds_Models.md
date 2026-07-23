# Match Events & Odds Models

> 53 nodes

## Key Concepts

- **test_pages.py** (33 connections) — `backend/tests/test_pages.py`
- **LolMatchEvent** (23 connections) — `backend/app/models_lol.py`
- **lol_api.py** (21 connections) — `backend/app/routers/lol_api.py`
- **synchronize_known_aliases()** (17 connections) — `backend/app/services/lol_team_aliases.py`
- **lol_team_aliases.py** (16 connections) — `backend/app/services/lol_team_aliases.py`
- **lol_odds_importer.py** (12 connections) — `backend/app/services/lol_odds_importer.py`
- **import_odds_csv()** (11 connections) — `backend/app/services/lol_odds_importer.py`
- **canonical_team()** (10 connections) — `backend/app/services/lol_team_aliases.py`
- **LolTeamAlias** (9 connections) — `backend/app/models_lol.py`
- **_match_view()** (8 connections) — `backend/app/routers/lol_api.py`
- **LolOddsSnapshot** (7 connections) — `backend/app/models_lol.py`
- **LolTeamOdd** (7 connections) — `backend/app/models_lol.py`
- **upcoming_matches()** (7 connections) — `backend/app/routers/lol_api.py`
- **normalize_text()** (7 connections) — `backend/app/services/lol_team_aliases.py`
- **_utc_iso()** (6 connections) — `backend/app/routers/lol_api.py`
- **_competition_code()** (6 connections) — `backend/app/routers/lol_api.py`
- **_odds_for_match()** (6 connections) — `backend/app/routers/lol_api.py`
- **Session** (5 connections)
- **_captured()** (5 connections) — `backend/app/services/lol_odds_importer.py`
- **import_odds_directory()** (5 connections) — `backend/app/services/lol_odds_importer.py`
- **resolve_team_alias()** (5 connections) — `backend/app/services/lol_team_aliases.py`
- **_competition_summary()** (4 connections) — `backend/app/routers/lol_api.py`
- **get_match()** (4 connections) — `backend/app/routers/lol_api.py`
- **Session** (4 connections)
- **upsert_alias()** (4 connections) — `backend/app/services/lol_team_aliases.py`
- *... and 28 more nodes in this community*

## Relationships

- [Core LoL Domain Models](Core_LoL_Domain_Models.md) (21 shared connections)
- [Oracle's Elixir Importer](Oracle%27s_Elixir_Importer.md) (11 shared connections)
- [Data Import Pipeline](Data_Import_Pipeline.md) (10 shared connections)
- [Match Statistics Engine](Match_Statistics_Engine.md) (9 shared connections)
- [Database & Migrations](Database_%26_Migrations.md) (7 shared connections)
- [Background Worker Jobs](Background_Worker_Jobs.md) (4 shared connections)
- [Team Logo Sync Service](Team_Logo_Sync_Service.md) (2 shared connections)
- [Config, HTTP & Utils](Config%2C_HTTP_%26_Utils.md) (1 shared connections)

## Source Files

- `backend/app/models_lol.py`
- `backend/app/routers/lol_api.py`
- `backend/app/services/lol_odds_importer.py`
- `backend/app/services/lol_team_aliases.py`
- `backend/tests/test_pages.py`

## Audit Trail

- EXTRACTED: 265 (92%)
- INFERRED: 22 (8%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*