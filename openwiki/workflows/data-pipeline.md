# Data Pipeline

## Overview

Pirapire's data pipeline ingests sports odds from Aposta.LA, enriches them with historical/fresh data from external APIs, computes descriptive statistics, and generates betting recommendations. The pipeline runs both on-demand (user-triggered via UI) and on a schedule (APScheduler in the worker container).

```
Aposta.LA ──→ Aposta Sync ──→ ImportedOdds ──→ Event Lifecycle ──→ Refresh Queue
                    │                                        │
                    ▼                                        ▼
           Historical Ingestion ◄─────────────────── Descriptive Stats
           Fresh Football                                    │
                    │                                        ▼
                    └──────────────────────────→ Recommender ──→ Dashboard
```

## 1. Aposta Sync

**Entry points:**
- Manual: UI button "Sincronizar Aposta.LA" → `POST /api/aposta/sync`
- Scheduled: worker runs `run_aposta_sync()` every 12 minutes

**Service:** `backend/app/services/aposta_sync.py` (19K lines)

**Flow:**
1. Fetches odds from Aposta.LA (currently CSV-based via `aposta_import_dir`; browser fetch via Playwright is configurable but not active by default)
2. Parses odds into `ImportedOdds` rows (football and LoL)
3. Maps markets to the canonical `MarketCatalog` via `market_matcher.py`
4. Creates/updates `ApostaEvent` records with canonical `event_key`
5. Builds `CaptureSnapshot` for the current odds state
6. Triggers event lifecycle reconciliation (Phase 4D1)
7. Optionally auto-triggers recommender recalculation

**Key config:** `APOSTA_SYNC_ENABLED`, `APOSTA_IMPORT_DIR` (`/app/data/imports/aposta`), `AUTO_RECOMMEND_ON_APOSTA_SYNC`

## 2. Historical Ingestion

**Entry points:**
- Manual: `POST /api/sources/sync/football` (via UI "Actualizar Fútbol")
- Scheduled: worker runs `run_historical_ingestion()` every 4 hours

**Service:** `backend/app/services/historical_ingestion.py` (55K — largest service file)

**Flow:**
1. Identifies active participants (teams with Aposta odds) from `ImportedOdds`
2. Fetches historical match data from configured football sources:
   - **Primary:** football-data.org v4 (`football_data_org.py`, rank 90)
   - **Secondary:** API-Football v3 (`api_football.py`, rank 88)
   - **Fallback:** OpenLigaDB (`openligadb.py`, free, rank 70), TheSportsDB (rank 60)
3. Stores matches in `FootballMatch`, teams in `FootballTeam`, competitions in `FootballCompetition`, standings in `FootballStanding`
4. Respects per-source rate limits (configurable delays, retry-after headers, max entities per run)
5. Uses strict per-event history windows (Phase 4B41): only matches within a configurable lookback window, excluding the anchor match itself

**Key config:** `FOOTBALL_DATA_API_KEY`, `FOOTBALL_DATA_REQUEST_DELAY_SECONDS` (7.0s), `FOOTBALL_DATA_MAX_COMPETITIONS_PER_RUN` (3), `SYNC_DEFAULT_LOOKBACK_DAYS` (45)

## 3. Fresh Football

**Entry points:**
- Scheduled: worker runs `run_fresh_football()` (APScheduler job)
- Triggered by: historical ingestion completion

**Service:** `backend/app/services/fresh_football.py` (24K)

**Purpose:** Complement historical ingestion with recent/fresh match data for teams with active Aposta odds. Uses a dual-source approach:
1. **Primary:** football-data.org v4 (recent matches endpoint)
2. **Fallback:** SofaScore public pages via browser worker (Playwright renders public team pages, extracts match data, statistics, and penalty info)

**Phase 4B4:** The fresh football window provides recent form data needed for descriptive statistics when historical data is insufficient or stale.

**Key config:** `SOFASCORE_WORKER_URL` (`http://pirapire_browser:8080`)

## 4. Event Lifecycle (Phase 4D1)

**Service:** `backend/app/services/event_lifecycle.py`

Runs after every Aposta sync. Derives a `local_event_state` for each `ApostaEvent`:

| State | Meaning |
|-------|---------|
| `scheduled` | Kickoff is >1h in the future, has active snapshot and odds. **Only these show as "Próximos" on dashboard.** |
| `live` | Kickoff within the last 4 hours |
| `finished` | Kickoff >4h ago or status=expired |
| `unknown_time` | No kickoff timestamp, but snapshot is current |
| `stale` | No current snapshot (snapshot expired/absent) |
| `expired` | Explicitly expired |
| `historical` | Archived |

The lifecycle also computes a diff (added/removed/kickoff_changed/participants_changed/markets_changed/unchanged) and enqueues changed events into the refresh queue.

## 5. Refresh Queue (Phase 4D1)

**Service:** `backend/app/services/refresh_queue.py`

Coalesced per-event queue. Multiple sync cycles before the worker picks up a task overwrite the same row with the most recent state. Only changed events are enqueued. The worker:
1. Claims tasks one at a time (instance-locked via `locked_by`)
2. Runs `descriptive_stats.compute_event()` for each
3. Releases the task lock
4. Processes up to 5 tasks per cycle

## 6. Descriptive Statistics (Phase 4C)

**Service:** `backend/app/services/descriptive_stats.py` (25K)

Computes read-model statistics for events:
- **Football:** mean goals (total, home, away, first half, second half), W/D/L percentages, over/under probabilities, both-teams-to-score rates
- **LoL:** map wins, player facts (last 5 series), team performance metrics

**Endpoints:**
- `GET /api/events/{event_key}` — returns descriptive stats alongside odds
- Rebuilt incrementally via refresh queue (Phase 4D1) or fully via `rebuild_all()`

## 7. Recommendations

**Service:** `backend/app/services/recommender/recommendation_service.py` (14K)

**Entry points:**
- UI: "Recalcular recomendaciones" button
- Auto: after Aposta sync (if `AUTO_RECOMMEND_ON_APOSTA_SYNC=true`)

**Flow:**
1. `probability_engine.py` — estimates fair probability for each selection using historical data
2. `odds_engine.py` — calculates implied probability, edge, and risk labels
3. `ranking.py` — ranks selections by one of four modes:
   - `probability` — highest model probability
   - `profit` (EV) — highest expected value
   - `odds` — highest decimal odds
   - `balanced` — composite score
4. `combo_builder.py` — builds combination bets (no same-event mixing, max legs configurable)
5. Results stored in `BetRecommendation` and `ComboRecommendation` tables

**Key config:** `RECOMMENDER_DEFAULT_MODE` (default: `probability`), `RECOMMENDER_EVENT_GRACE_MINUTES` (30)

## Scheduled jobs (worker_main.py)

| Job | Interval | Function |
|-----|----------|----------|
| Aposta sync | 12 min | `run_aposta_sync()` |
| Sports data sync | 4 hours | `run_historical_ingestion()` |
| WC squad sync | 24 hours | `run_wc_squad_sync()` |
| Fresh football | 30 min | `run_fresh_football()` |
| Descriptive stats | 4 hours | `run_descriptive_stats()` |
| Event refresh | 2 min | `run_event_refresh()` (lifecycle + refresh queue) |

All jobs use `coalesce=True` and `max_instances=1` to prevent overlap.
