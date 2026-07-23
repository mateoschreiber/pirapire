# Data Pipeline

Pirapire ingests data from four sources to serve the competitive dashboard and match detail pages.

## 1. Leaguepedia Schedule Sync

**Service:** `backend/app/services/sync/lol_sync.py`

The worker job `sync_schedule` fetches upcoming matches from the **Leaguepedia Cargo API** (MediaWiki-based wiki for competitive LoL).

- **Query table:** `MatchSchedule` with fields `Team1, Team2, DateTime_UTC, MatchId, BestOf, Winner, OverviewPage`
- **Window:** 6 hours in the past to `leaguepedia_import_lookahead_days` (default 14) in the future
- **Pagination:** 500 rows per page, fetches all pages
- **Key logic:** Parses team names, creates `LolMatchEvent` records with a deterministic `match_key` (SHA-256 hash of `source_name:source_match_id`, truncated to 16 chars)
- **Academy exclusion:** League names containing "CL" (Challengers) are filtered out — only tier-1 leagues compete in the dashboard
- **Team normalization:** Uses `canonical_league()` from `lol_league_catalog.py` to map league names to canonical slugs

Also syncs Data Dragon via `sync_datadragon` for champion/version metadata.

## 2. Odds CSV Import

**Service:** `backend/app/services/lol_odds_importer.py`

The worker job `import_odds` (every 5 min) polls the odds inbox directory for CSV files.

**CSV format:**
```csv
match_key,team_name,decimal_odds,provider,captured_at
LCK_2025_T1_GEN,T1,1.85,manual,2025-06-01T12:00:00Z
LCK_2025_T1_GEN,Gen.G,1.95,manual,2025-06-01T12:00:00Z
```

**Validation rules:**
- Required columns: `match_key`, `team_name`, `decimal_odds`
- `decimal_odds` must be > 1.0
- Exactly 2 teams per match_key (no duplicates)
- Teams must resolve to one side of an existing `LolMatchEvent`
- `captured_at` parsed flexibly (ISO formats); defaults to now

**Processing:**
1. Parse CSV, group by `(match_key, provider, captured_at)` tuple
2. Resolve team names via `lol_team_aliases.resolve_team_alias()`
3. Mark previous snapshot for this match/provider as `is_current=False`
4. Create new `LolOddsSnapshot` + `LolTeamOdd` records
5. Move file to `processed/` directory

## 3. Oracle's Elixir CSV Import

**Services:**
- Local inbox: `backend/app/services/imports/oracles_elixir_importer.py`
- Remote download: `backend/app/services/imports/remote_oracles_elixir.py`
- Series builder: `backend/app/services/series_builder.py`

The worker jobs `import_oracles` (every 30 min for local inbox) and `sync_remote_oracles` (every `lol_history_remote_poll_minutes`, default 60 min) handle Oracle's Elixir data ingestion.

### Local Inbox Processing

The worker polls the Oracle's Elixir inbox directory for CSV files.

**Oracle's Elixir** provides detailed competitive match data (every professional game globally). Each CSV row represents one participant (team or player) in one game.

**Processing:**
1. Scan `inbox/` directory for `.csv` files
2. Normalize headers (lowercase, remove spaces/underscores)
3. Group rows by `gameid`
4. Split each game into team rows (position="team") and player rows
5. Upsert `LolGameHistory`, `LolTeamGameStat`, `LolPlayerGameStat` records
6. Skip already-imported games (dedup by `source_key`)
7. Move file to `processed/` or `errors/`

**Replacement mode:** The upload API supports `replace_existing=true` which atomically deletes all existing data for the file's years before re-importing.

### Remote Oracle Sync

**Service:** `backend/app/services/imports/remote_oracles_elixir.py`

The worker job `sync_remote_oracles` polls a configured remote URL (e.g., Google Drive share) for updated Oracle's Elixir CSVs.

**Remote download flow:**
1. Google Drive share links are auto-converted to direct download URLs via `google_drive_download_url()`
2. CSV is streamed to a temp file with size validation (`lol_history_remote_max_mb`, default 100 MB)
3. Content is validated: checks for Google Drive quota pages, HTML responses, empty files, and required CSV headers
4. SHA-256 checksum is computed and compared against the last imported version (stored in source config)
5. If unchanged, the run is marked as `skipped` with no re-import
6. If changed, `_import_csv_file()` runs with `replace=True, prune_missing=False`, then `rebuild_series()` is called

**Workflow diagram:**
```
Remote URL → google_drive_download_url() → stream download → validate → SHA-256 check
    │
    ├── unchanged → skipped (no-op)
    └── changed  → _import_csv_file(replace=True) → rebuild_series()
```

**Configuration:** Set via the admin UI at `/sources` → Oracle's Elixir → configure `base_url` and enable `auto_refresh`. The setting persists in the `DataSource.config_json` field. Manual sync can be requested via `POST /api/sources/oracles_elixir/sync`.

## 4. Series Builder

**Service:** `backend/app/services/series_builder.py`

After Oracle's Elixir data is imported, `rebuild_series()` groups individual `LolGameHistory` records into `LolSeries` records.

**Grouping logic:**
1. Sort all games by date
2. Bucket games by `(league, date, sorted_team_pair)`
3. Sort games within each bucket chronologically
4. Create a `LolSeries` with team scores, best-of determination (1/3/5), game count
5. Link games to series via `series_id` foreign key
6. Generate unique `series_key` (SHA-256 of league+date+teams+source, 24-char hex)

**Key constraint:** Only Oracle's Elixir games have `LolSeries` records. Schedule-only series from Leaguepedia don't create series entries, preventing partial/stale data in metrics.

## 5. Statistics Precomputation

**Service:** `backend/app/services/lol_metrics_engine.py`

The metrics engine computes **team and player statistics** from recent completed series.

**For each upcoming match:**
1. Resolve both team names via `lol_team_aliases.canonical_team()`
2. Find last 5 complete `LolSeries` per team (Oracle's Elixir only, strictly before match start)
3. Load `LolTeamGameStat` rows for those series
4. Compute per-series win/loss records (aggregated from individual map results) and a **win_rate_pct** for each team
5. Compute both percentage shares and absolute per-map averages for towers, inhibitors, kills, deaths, dragons, barons, gold
6. Compute average map/series duration
7. Compute per-player metrics: kills, deaths, gold per map, CS per map (absolute values)
8. Run `_estimated_market()` to produce **form-based fair odds** for both teams using Laplace-smoothed relative probability

**Coverage labels:** `complete`, `partial`, or `unavailable` — visible in the match detail UI as "Completo", "Parcial", or "N/D". The response also includes `estimated_market` (form-based odds) and `data_notes` with context about the source of odds and sample window.

Statistics are now **cached** in `LolMatchStatisticsReadModel`. The worker's `precompute_stats` job (every 30 min, runs immediately on start) calls `precompute_upcoming_stats()` which persists computed results via `store_match_statistics()`. Subsequent loads serve from cache (validated by `input_fingerprint`). Cache is invalidated on series rebuilds, schedule syncs, and Oracle's Elixir imports. See [domain/lol-metrics.md → Statistics Cache & Precomputation](../domain/lol-metrics.md#statistics-cache--precomputation).

## 6. Dashboard & API Serving

- **Upcoming matches API** (`/api/lol/matches/upcoming`): Fetches `LolMatchEvent` records within configurable window, enriches with odds from `LolOddsSnapshot`/`LolTeamOdd`
- **Match preview odds** — The upcoming API response now includes `estimated_market` directly on each match view, batch-loaded from the statistics cache via `cached_statistics_from_record()`. The dashboard renders these inline with `oddsHtml()` — no separate async fetch. See [domain/lol-metrics.md → Dashboard Preview Odds](../domain/lol-metrics.md#dashboard-preview-odds).
- **Competition filtering:** Dashboard shows only tier-1 leagues and international events
- **Competition classification** (`_competition_code()` in `lol_api.py`): Regex-based mapping of league/tournament strings to canonical codes (LCK, LPL, LEC, LCS, CBLOL, LCP, WORLDS, MSI, FIRST_STAND, EWC, KESPA)
