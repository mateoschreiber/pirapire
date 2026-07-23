# Team Logo Sync Service

> 15 nodes

## Key Concepts

- **sync_official_team_logos()** (10 connections) — `backend/app/services/team_logo_sync.py`
- **team_logo_sync.py** (7 connections) — `backend/app/services/team_logo_sync.py`
- **apply_display_aliases()** (5 connections) — `backend/app/services/team_logo_sync.py`
- **sync_team_logos.py** (4 connections) — `backend/scripts/sync_team_logos.py`
- **sync_known_official_assets()** (3 connections) — `backend/app/services/team_logo_sync.py`
- **team_logo_key()** (2 connections) — `backend/app/services/team_logo_sync.py`
- **_entries()** (2 connections) — `backend/app/services/team_logo_sync.py`
- **job_sync_team_logos()** (2 connections) — `backend/app/worker_main.py`
- **main()** (2 connections) — `backend/scripts/sync_team_logos.py`
- **test_logo_aliases_use_downloaded_official_assets()** (2 connections) — `backend/tests/test_pages.py`
- **Local cache for official team logos published by LoL Esports.** (1 connections) — `backend/app/services/team_logo_sync.py`
- **Map provider spelling variants to an already cached official logo.** (1 connections) — `backend/app/services/team_logo_sync.py`
- **Cache assets published by a team when it is not in Riot's current feed.** (1 connections) — `backend/app/services/team_logo_sync.py`
- **Refresh the local cache from official Riot LoL Esports pages.** (1 connections) — `backend/app/services/team_logo_sync.py`
- **Refresh local official LoL Esports logos.** (1 connections) — `backend/scripts/sync_team_logos.py`

## Relationships

- [Match Events & Odds Models](Match_Events_%26_Odds_Models.md) (2 shared connections)
- [Background Worker Jobs](Background_Worker_Jobs.md) (2 shared connections)

## Source Files

- `backend/app/services/team_logo_sync.py`
- `backend/app/worker_main.py`
- `backend/scripts/sync_team_logos.py`
- `backend/tests/test_pages.py`

## Audit Trail

- EXTRACTED: 44 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*