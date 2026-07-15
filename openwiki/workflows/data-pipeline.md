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

**Service:** `backend/app/services/imports/oracles_elixir_importer.py`

The worker job `import_oracles` (every 30 min) polls the Oracle's Elixir inbox directory.

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

**Dedup service** (`backend/oracles_elixir_importer.py`):
- Separate standalone deduplication script (not wired into the current pipeline)
- Groups games by `(league, date, team_a, team_b)` and keeps only the first 5 maps per pair
- Renames encountered duplicates with a `.processed` suffix

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
4. Compute percentage metrics: towers, inhibitors, kills, deaths, dragons, barons, gold (all as share of total)
5. Compute absolute metrics: game duration, series duration averages
6. Compute per-map player metrics: kills, deaths, gold, solo kills, CS
7. Store results in `LolMatchStatisticsReadModel` with an input fingerprint for cache validation

**Coverage labels:** `complete`, `partial`, or `unavailable` — visible in the match detail UI as "Completo", "Parcial", or "N/D".

## 6. Dashboard & API Serving

- **Upcoming matches API** (`/api/lol/matches/upcoming`): Fetches `LolMatchEvent` records within configurable window, enriches with odds from `LolOddsSnapshot`/`LolTeamOdd`
- **Competition filtering:** Dashboard shows only tier-1 leagues and international events
- **Competition classification** (`_competition_code()` in `lol_api.py`): Regex-based mapping of league/tournament strings to canonical codes (LCK, LPL, LEC, LTA, LCP, WORLDS, MSI, FIRST_STAND, EWC)
