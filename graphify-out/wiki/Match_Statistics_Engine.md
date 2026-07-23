# Match Statistics Engine

> 17 nodes

## Key Concepts

- **lol_metrics_engine.py** (21 connections) — `backend/app/services/lol_metrics_engine.py`
- **_team_payload()** (9 connections) — `backend/app/services/lol_metrics_engine.py`
- **Session** (8 connections)
- **_recent_matchups()** (8 connections) — `backend/app/services/lol_metrics_engine.py`
- **compute_match_statistics()** (8 connections) — `backend/app/services/lol_metrics_engine.py`
- **LolSeries** (7 connections) — `backend/app/models_lol.py`
- **_resolve()** (6 connections) — `backend/app/services/lol_metrics_engine.py`
- **_recent_series()** (5 connections) — `backend/app/services/lol_metrics_engine.py`
- **_series_games()** (5 connections) — `backend/app/services/lol_metrics_engine.py`
- **_players()** (5 connections) — `backend/app/services/lol_metrics_engine.py`
- **_estimated_market()** (4 connections) — `backend/app/services/lol_metrics_engine.py`
- **precompute_upcoming_stats()** (4 connections) — `backend/app/services/lol_metrics_engine.py`
- **datetime** (3 connections)
- **test_estimated_market_uses_both_teams_recent_series()** (2 connections) — `backend/tests/test_pages.py`
- **_metric()** (1 connections) — `backend/app/services/lol_metrics_engine.py`
- **Traceable, series-based LoL statistics.** (1 connections) — `backend/app/services/lol_metrics_engine.py`
- **Return the last three individual maps, never series aggregates.** (1 connections) — `backend/app/services/lol_metrics_engine.py`

## Relationships

- [Match Events & Odds Models](Match_Events_%26_Odds_Models.md) (9 shared connections)
- [Oracle's Elixir Importer](Oracle%27s_Elixir_Importer.md) (7 shared connections)
- [Core LoL Domain Models](Core_LoL_Domain_Models.md) (5 shared connections)
- [Background Worker Jobs](Background_Worker_Jobs.md) (3 shared connections)

## Source Files

- `backend/app/models_lol.py`
- `backend/app/services/lol_metrics_engine.py`
- `backend/tests/test_pages.py`

## Audit Trail

- EXTRACTED: 91 (93%)
- INFERRED: 7 (7%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*