# Integrations

Pirapire integrates with four external data sources to serve the competitive LoL dashboard.

## 1. Leaguepedia Cargo API

**URL:** `https://lol.fandom.com/wiki/Special:CargoExport`  
**Service:** `backend/app/services/sync/lol_sync.py`  
**Config:** `LEAGUEPEDIA_BASE_URL`, `LEAGUEPEDIA_USER_AGENT`

Fetches the professional match schedule via MediaWiki's Cargo extension.

- **Table:** `MatchSchedule`
- **Fields:** `Team1, Team2, DateTime_UTC, MatchId, BestOf, Winner, OverviewPage`
- **Window:** 6 hours past → `leaguepedia_import_lookahead_days` (default 14) ahead
- **Rate limit:** 500 rows per page, sequential paging
- **Auth:** None (public API, User-Agent header only)

**What gets stored:** `LolMatchEvent` records for upcoming and recent-finished matches.

## 2. Riot Data Dragon

**URL:** `https://ddragon.leagueoflegends.com`  
**Client:** `backend/app/sources/lol/datadragon.py`  
**Config:** `DATADRAGON_BASE_URL`, `DATADRAGON_LOCALE`

Static game data (champion names, versions) updated every patch cycle.

- `get_versions()` — Fetches available game versions list
- `get_champions(version, locale)` — Fetches champion.json for a version
- Uses the shared `http_client` (httpx wrapper with timeout + retry)

**What gets stored:** `LolPatch` and `LolChampion` reference records.

## 3. Oracle's Elixir CSV

**URL:** `https://oracleselixir.com/tools/downloads` (download site)  
**Local importer:** `backend/app/services/imports/oracles_elixir_importer.py`  
**Remote downloader:** `backend/app/services/imports/remote_oracles_elixir.py`  
**Config:** `LOL_HISTORY_IMPORT_DIR`, `LOL_HISTORY_REMOTE_MAX_MB`

Oracle's Elixir provides the most comprehensive competitive LoL dataset (every professional game globally, with team and player stats).

**Import method (local):** CSV files placed in `{import_dir}/inbox/` are picked up by the worker.

**Import method (remote):** A configured remote URL (Google Drive share or direct CSV) is polled every `lol_history_remote_poll_minutes` (default 60). The downloader performs SHA-256 comparison and only re-imports when the content changes.

**CSV columns expected:** `gameid`, `position`, `teamname`, `date`, `league`, etc.

**Upload API:** `POST /api/sources/oracles/upload` (admin-auth protected, max 100 MB, CSV or ZIP).

**Google Drive support:** Share links like `https://drive.google.com/file/d/{id}/view` are automatically converted to direct download URLs by `google_drive_download_url()`.

**Remote validation:** The downloader checks for quota-exceeded pages, HTML responses (instead of CSV), and empty files. It validates that required OE headers (`gameid`, `position`, `teamname`) are present.

**Processing detail:** See [Data Pipeline](/openwiki/workflows/data-pipeline.md#3-oracles-elixir-csv-import).

## 4. Manual Odds CSV

**Service:** `backend/app/services/lol_odds_importer.py`  
**Config:** `LOL_ODDS_IMPORT_DIR`

CSV files with decimal odds for upcoming matches, placed in `{odds_dir}/inbox/`.

**CSV columns:** `match_key`, `team_name`, `decimal_odds`, `provider`, `captured_at`

See [Data Pipeline: Odds Import](/openwiki/workflows/data-pipeline.md#2-odds-csv-import) for format details.

## 5. HTTP Client

**Service:** `backend/app/services/http_client.py`

Shared httpx wrapper for all external HTTP calls:

- **Timeout configuration:** connect=5s, read=20s, write=5s, pool=5s (configurable via env)
- **Retries:** 2 retries via httpx transport
- **User-Agent:** `PirapireLocal/1.0`
- **Structured response:** `request_json()` returns `{ok, status, data, error, retry_after}` (never raises)

## Source Status Tracking

**Service:** `backend/app/routers/sources.py`  
**Models:** `DataSource`, `SourceRun`, `ImportBatch`, `ImportError`

The `/api/sources` endpoints expose status for all defined data sources:

| Source Code | Display Name | Configured | Enabled | Notes |
|-------------|-------------|-----------|---------|-------|
| `leaguepedia_schedule` | Leaguepedia Schedule | — | ✓ | Managed by runtime (`.env` config), not via admin UI |
| `leaguepedia_statistics` | Leaguepedia Statistics | — | — | Not currently implemented |
| `oracles_elixir` | Oracle's Elixir | ✓ | ✓ | Supports remote URL sync (Google Drive), local inbox uploads, and `auto_refresh` toggle |
| `riot_datadragon` | Riot Data Dragon | — | — | Always-on via scheduler, no admin config needed |
| `manual_odds_csv` | Manual odds CSV | — | — | Inbox-picked by worker |
| `external_odds_api` | External odds API | — | — | Placeholder for future external odds provider integration |

The admin UI at `/sources` allows monitoring runs, uploading CSV files, viewing import history, configuring the Oracle remote URL, and testing source connectivity.
