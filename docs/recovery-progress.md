# Pirapire Recovery Baseline R0
**Date:** 2026-07-10 19:12 UTC
**Commit:** 88dbb82 (Act6)
**Branch:** main (clean)

## Backup
- File: data/r0_backup_20260710_191251.db
- Size: 26.5 MB
- Integrity: ok (VACUUM INTO)

## Counts
| Entity | Count |
|--------|-------|
| importedodds (aposta) | 45,228 |
| footballmatch | 104 (97 FINISHED, 7 TIMED) |
| footballteam | 143 |
| footballplayer | 1,249 |
| lolgamehistory | 480 |
| lolteamgamestat | 962 |
| lolplayergamestat | 500 |
| betrecommendation | 55 |
| current_odds_football | 10 |
| current_odds_lol | 890 |
| active_events | 7 |

## Code Health
| Check | Result |
|-------|--------|
| compileall | OK |
| ruff | 83 warnings (not 773 as previously estimated) |
| pytest | FAILED (disk I/O error on conftest) |
| node --check | NOT AVAILABLE (Node.js not installed in host or container) |

## Issues
1. P2: events.router registered 3x (main.py:85-87)
2. P2: 3 functions in events.py (expected 2)
3. P3: Dead tables sport/team/match/oddssnapshot/prediction (0 rows)
4. P3: ruff 83 warnings (not 773)

## Containers
- pirapire_app: healthy
- pirapire_worker: running
- pirapire_browser: healthy

---

# R0B — Baseline Diagnostics (2026-07-10)
**Phase:** R0B — Read-only diagnostics, no code/data changes

## 1. node --check backend/app/static/js/app.js
**Result:** NOT EXECUTABLE
Node.js is not installed on the host (`node: command not found`) nor in the pirapire_app container (`exec: "node": executable file not found in $PATH`).

## 2. compileall
**Result:** OK (20/20 test files compiled successfully)
All test files in `backend/tests/` compile without syntax errors.

## 3. pytest -q
**Result:** CRASH (disk I/O error)
Trace: `sqlite3.OperationalError: disk I/O error` on `CREATE INDEX ix_footballcompetition_source_name` during `conftest.py:init_db()`.
Tests do not even start — conftest database initialization fails.
- **passed:** 0
- **failed:** 0 (startup crash)
- **errors:** 1 (conftest init_db disk I/O)

## 4. ruff check (--statistics)
**Result:** 83 violations (11 rules) — NOT 773 as previously documented

| Code | Count | Description |
|------|-------|-------------|
| F401 | 32 | unused-import [*] |
| E701 | 10 | multiple-statements-on-one-line-colon |
| E712 | 10 | true-false-comparison [*] |
| F821 | 10 | undefined-name |
| E702 | 8  | multiple-statements-on-one-line-semicolon |
| E401 | 3  | multiple-imports-on-one-line [*] |
| E722 | 3  | bare-except |
| E402 | 2  | module-import-not-at-top-of-file |
| E741 | 2  | ambiguous-variable-name |
| F811 | 2  | redefined-while-unused |
| F841 | 1  | unused-variable [*] |

[*] fixable with `ruff check --fix`

## 5. Route Listing (83 total, 5 duplicate pairs)

| Path | Method | File(s) | Dup |
|------|--------|---------|-----|
| / | GET | pages.py | |
| /aliases | GET | markets.py | |
| /analyze | POST | combo.py, odds.py | x2 |
| /aposta/ui | GET | pages.py | |
| /backtest | GET | dashboard.py | |
| /bets | GET | recommendations.py | |
| /calendar | GET | dashboard.py | |
| /capabilities | GET | sources.py | |
| /combo/ui | GET | pages.py | |
| /combos | GET | recommendations.py | |
| /combos/{combo_id}/save-to-history | POST | recommendations.py | |
| /coverage | GET | lol_history.py | |
| /data/football/ui | GET | pages.py | |
| /data/lol/ui | GET | pages.py | |
| /events | GET | aposta.py | |
| **/events/{event_id}** | **GET** | **pages.py (x2)** | **x2** |
| /football/competitions | GET | data.py | |
| /football/matches | GET | data.py | |
| /football/standings | GET | data.py | |
| /football/status | GET | data.py | |
| /football/teams | GET | data.py | |
| /health | GET | health.py | |
| /history/combos | GET | history.py | |
| /history/combos/{combo_id}/settle | POST | history.py | |
| /history/predictions | GET | history.py | |
| /history/predictions/{prediction_id}/settle | POST | history.py | |
| /history/ui | GET | pages.py | |
| /import | POST | lol_history.py | |
| /import-year/{year} | POST | lol_history.py | |
| /imports/aposta-odds-csv | POST | imports.py | |
| /imports/batches | GET | imports.py | |
| /imports/batches/{batch_id} | GET | imports.py | |
| /imports/batches/{batch_id}/errors | GET | imports.py | |
| /imports/oracles-elixir-csv | POST | imports.py | |
| /imports/templates/aposta-odds | GET | imports.py | |
| /imports/templates/oracles-elixir | GET | imports.py | |
| /imports/ui | GET | pages.py | |
| /latest | GET | recommendations.py | |
| /leagues | GET | lol_history.py | |
| /lol/champions | GET | data.py | |
| /lol/patches | GET | data.py | |
| /markets | GET | aposta.py | |
| /markets/ui | GET | pages.py | |
| /matches/ui | GET | pages.py | |
| /odds/imported | GET | imports.py | |
| /odds/ui | GET | pages.py | |
| /options | GET | aposta.py | |
| /player-metrics | GET | lol_history.py | |
| /rankings | GET | sources.py | |
| /raw-snapshots | GET | source_runs.py | |
| /recommendations/ui | GET | pages.py | |
| /refresh | POST | dashboard.py | |
| /run | POST | recommendations.py | |
| /seed | POST | markets.py, sources.py | x2 |
| /selections | GET | aposta.py | |
| /settings/ui | GET | pages.py | |
| /source-runs | GET | source_runs.py | |
| /source-runs/ui | GET | pages.py | |
| /source-runs/{run_id} | GET | source_runs.py | |
| /source-runs/{run_id}/logs | GET | source_runs.py | |
| /sources/ui | GET | pages.py | |
| /sports/ui | GET | pages.py | |
| /state | GET | dashboard.py | |
| /status | GET | aposta.py, lol_history.py | x2 |
| /sync | POST | aposta.py | |
| /sync-and-recommend | POST | aposta.py | |
| /sync-runs | GET | aposta.py | |
| /sync/all | POST | sources.py | |
| /sync/football | POST | sources.py | |
| /sync/lol | POST | sources.py | |
| /sync/{source_slug} | POST | sources.py | |
| /team-metrics | GET | lol_history.py | |
| /teams/ui | GET | pages.py | |
| /unmapped-markets | GET | aposta.py | |
| **/{event_id}** | GET | events.py | |
| **/{event_id}/statistics** | **GET** | **events.py (x2)** | **x2** |
| /{market_id} | GET | markets.py | |
| /{recommendation_id}/save-to-history | POST | recommendations.py | |

**5 duplicate pairs** (3 inter-file intentional, 2 intra-file bugs):
- `/analyze` POST: combo.py + odds.py (different routers, different prefix — likely intentional)
- `/events/{event_id}` GET: pages.py x2 (BUG — same file, line 239 vs 263)
- `/seed` POST: markets.py + sources.py (different routers — likely intentional)
- `/status` GET: aposta.py + lol_history.py (different routers — likely intentional)
- `/{event_id}/statistics` GET: events.py x2 (BUG — same file, line 78 vs 175)

## 6. Duplicate Decorators

### pages.py (lines 239-264)
```
Line 239: @router.get("/events/{event_id}", response_class=HTMLResponse)
Line 240: def event_detail_page(request: Request, event_id: int):  # v1: ImportedOdds.id == event_id
Line 263: @router.get("/events/{event_id}", response_class=HTMLResponse)
Line 264: def event_detail_page(request: Request, event_id: int):  # v2: ImportedOdds.matched_event_id == event_id
```
Two identical function names `event_detail_page` with same route. Only the last one (v2, matched_event_id) survives in FastAPI registration.

### events.py (lines 78-175)
```
Line 78:  @router.get("/{event_id}/statistics")
Line 79:  def event_statistics(...):  # v1: complete, uses event_id directly
Line 172:     return event            # ORPHANED unreachable code (after return stats)
Line 173:     event["market_count"] = len(market_list)  # ORPHANED unreachable code
Line 175: @router.get("/{event_id}/statistics")
Line 176: def event_statistics(...):  # v2: duplicate, identical to v1
Line 269:     return event            # ORPHANED unreachable code (after return stats)
```
- `event_statistics` defined twice — only last definition (v2) is active
- Orphaned `return event` and `event["market_count"] = len(market_list)` at lines 172-173 are inside v1 function body after `return stats` (dead code, not syntax error)
- Orphaned `return event` at line 269 inside v2 function body after `return stats` (dead code)

## 7. Router Registration in main.py (lines 72-88)
All routers registered once **EXCEPT** `events.router`:
```
Line 85: app.include_router(events.router)
Line 86: app.include_router(events.router)  # DUPLICATE
Line 87: app.include_router(events.router)  # DUPLICATE
```
Effect: All event routes are registered 3x. Since the duplicate `event_statistics` function also overwrites itself, effective routes from events.py are:
- `GET /{event_id}` — registered 3x (but only 1 handler defined, served 3 ways)
- `GET /{event_id}/statistics` — registered 6x (3 duplicates x 2 handlers → last v2 wins)

## 8. Template Validation

### base.html (backend/app/templates/base.html)
- **MISSING `<main>` OPEN TAG:** The `{% block content %}{% endblock %}` is placed between a closing `</div>` and `</main>`:
  ```html
  <div id="flash" class="flash" hidden></div>
  {% block content %}{% endblock %}
  </main>
  ```
  There is NO corresponding `<main>` opening tag anywhere in the file. This causes invalid HTML structure.
- The sidebar navigation has no link for markets, imports, aposta, recommendations, sources, or events pages (only Inicio, Futbol, LoL, Equipos, Historial, Config).

### event_detail.html (backend/app/templates/event_detail.html)
- **CORRUPTED — Content duplicated 3 times:**
  - `{% block title %}` is incomplete (missing `%}`)
  - `{% block header %}` references a block not defined in base.html
  - After `{% endblock %}` (line ~20), the entire stats section + JS is duplicated outside any block
  - Inside `{% block content %}`, the stats section + JS appears again
  - Inside `{% block scripts %}`, the stats section + JS appears a third time
- Same HTML section (`<section class="card" id="stats-section">...`) and JS fetch code appear 3 times total
- The `{% block content %}` and `{% block scripts %}` sections are structurally valid but contain duplicated stats code

## 9. Active Events (7)

| # | ID | Sport | Team A | Team B | Competition | Kickoff (UTC) | Markets | Odds |
|---|-----|-------|--------|--------|-------------|---------------|---------|------|
| 1 | 44333 | football | Noruega | Inglaterra | Copa del Mundo | 2026-07-11T18:00 | 2 (match_winner, total_goals) | 5 |
| 2 | 44338 | football | Argentina | Suiza | Copa del Mundo | 2026-07-11T22:00 | 2 (match_winner, total_goals) | 5 |
| 3 | 44343 | lol | Malvinas | Seven Dark | LRS | 2026-07-10T20:00 | 4 | 16 |
| 4 | 44359 | lol | Volticons | Golden Lions | LRS | 2026-07-10T20:00 | 4 | 18 |
| 5 | 44377 | lol | 9z Team | ZEN Esports | LRS | 2026-07-10T23:00 | 4 | 16 |
| 6 | 44393 | lol | Maze Gaming | Docta Esports Club | LRS | 2026-07-10T23:00 | 4 | 18 |
| 7 | 44411 | lol | Hanwha Life Esports | Lyon Gaming | MSI | 2026-07-11T08:00 | 5 | 822 |

- Hanwha Life vs Lyon Gaming dominates with 822 odds rows (35 market variants) across kill props, map handicaps, player stats
- Both football events have only 2 markets with 5 odds rows each (very thin data)
- Total active odds rows: 900

## 10. Event Comparison (8 → 7)

The backup (`r0_backup_20260710_191251.db`) also contains exactly 7 active events — identical set. No event disappeared between backup and current state.

There are 10 recently expired events (`is_current=0`) in the database, all football friendlies that fell out of the active window naturally:
- Benfica vs Flamengo, Panathinaikos vs Grasshoppers, Accrington Stanley vs Blackburn, etc.
- These were never in the backup's active set, so the "8 → 7" transition predates the R0 backup.

**Hypothesis:** An 8th active event existed before the backup was taken and was correctly marked `is_current=0` during Aposta sync. The system correctly expires events — no data loss or orphaned events detected. Total distinct events ever in DB: 106.

## 11. Data Anomaly
- **Argentina vs Suiza** and **Noruega vs Inglaterra** exist in the database with BOTH `is_current=1` and `is_current=0` rows — indicating potential sync race condition or incomplete update during the last sync cycle. This does not affect the active event count (7 unique) but indicates 2 events have stale duplicate rows.

## New Findings Summary (R0B)
1. **P1 — pytest broken:** Disk I/O error on test DB init blocks all tests
2. **P1 — Node.js missing:** Cannot validate frontend JS
3. **P2 — events.router 3x:** Confirmed registration bug at main.py:85-87
4. **P2 — event_detail_page duplicated:** pages.py:239 and pages.py:263 with different lookup logic
5. **P2 — event_statistics duplicated:** events.py:78 and events.py:175 with orphaned dead code
6. **P3 — base.html missing `<main>`:** Invalid HTML structure, no opening tag
7. **P3 — event_detail.html corrupted:** Content triplicated across 3 blocks, incomplete title block
8. **P3 — Data anomaly:** 2 events have both current and non-current rows
9. **P4 — ruff count discrepancy:** Previously documented as 773, actual count is 83 warnings
10. **P4 — 8→7 event delta:** No delta found in backup; transition predates R0 baseline
