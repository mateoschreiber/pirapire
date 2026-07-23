# LoL Domain Model

## Core Concepts

### Match Events (`LolMatchEvent`)

Represents a **professional LoL series** (upcoming or finished) sourced from Leaguepedia.

- `match_key`: Deterministic 16-char hex ID (`sha256(source_name:source_match_id)[:16]`)
- `team_a`, `team_b`: Team names as reported by Leaguepedia
- `start_time_utc`: UTC datetime of the series
- `best_of`: 1, 3, or 5 maps
- `status`: `scheduled` | `live` | `finished` | `cancelled` | `postponed`

### Series (`LolSeries`)

Groups individual **games** (maps) into a best-of series. Built from Oracle's Elixir data after import.

- `series_key` — Deterministic 24-char hex ID
- `team_a`, `team_b`, `score_a`, `score_b`
- `game_ids_json` — JSON array of `LolGameHistory` IDs
- `complete` — Boolean flag; only complete series are used for statistics
- `source_name` — Only `oracles_elixir` series are used for stats computation

### Game History (`LolGameHistory`, `LolTeamGameStat`, `LolPlayerGameStat`)

Per-map competitive data from Oracle's Elixir:

- **`LolGameHistory`:** Game metadata (league, date, patch, duration, winner, sides)
- **`LolTeamGameStat`:** Per-team stats per game (kills, deaths, towers, dragons, barons, gold, etc.)
- **`LolPlayerGameStat`:** Per-player stats per game (kills, deaths, assists, CS, damage, gold, etc.)

### Odds (`LolOddsSnapshot`, `LolTeamOdd`)

Immutable captures of decimal odds for a match:

- `LolOddsSnapshot` — One capture event (provider + timestamp), linked to a `LolMatchEvent`
- `LolTeamOdd` — One team's decimal odds within a snapshot
- `is_current` — Boolean marking the latest snapshot for a match/provider pair

## Statistics Engine

**Source:** `backend/app/services/lol_metrics_engine.py`

### Team Metrics

Computed from the last **5 complete Oracle's Elixir series** per team (strictly before match start):

The engine computes two representations of each metric:
- **Percentage share** (`metrics`): `V_t / (V_t + V_o)` — the team's share of the combined total with its opponent per map.
- **Absolute per-map average** (`averages`): sum of the team's values divided by maps played.

The **match detail UI displays only the absolute per-map averages** plus win rate, not the percentage shares:

| Metric | UI Label | Displayed Value |
|--------|----------|-----------------|
| Win Rate % | Porcentaje de victorias | `W / (W + L)`, where W = series won, L = series lost |
| Towers destroyed | Torres destruidas | Absolute per-map average |
| Inhibitors destroyed | Inhibidores destruidos | Absolute per-map average |
| Kills | Kills | Absolute per-map average |
| Deaths | Muertes | Absolute per-map average |
| Dragons killed | Dragones | Absolute per-map average |
| Barons killed | Barones | Absolute per-map average |
| Total Gold | Oro | Absolute per-map average |
| Avg Map Duration | Duración del mapa | Mean of `game_length_seconds` |
| Avg Series Duration | Duración de la serie | Sum of game durations per series |

Win rate is computed at the series level, not the map level. A series is "decided" when one team wins more maps than the other — tied series (e.g., 1-1 in BO2) are excluded from win-rate computation. The series-level win/loss is determined by comparing map results within each series. See `_team_payload()` in `backend/app/services/lol_metrics_engine.py` for the map-to-series aggregation logic.

### Player Metrics

Computed per player from the same recent series. The engine computes several internal fields, but the **match detail UI displays only these:**

| Metric | UI Column | Value Type |
|--------|-----------|------------|
| Kills | Asesinatos promedio por mapa | Average per map (total kills / maps played) |
| Deaths | Muertes promedio por mapa | Average per map (total deaths / maps played) |
| Gold Per Map | Oro promedio por mapa | Total gold / maps played |
| CS Per Map | CS promedio por mapa | Total creep score / maps with valid CS |
| Maps Played | Mapas jugados | Number of maps where this player appears |

(The engine also computes `kills_pct`, `deaths_pct`, and `gold_per_map` internally, but these are not rendered in the current UI.)

### Coverage Labels

- `complete` — All expected maps have valid data
- `partial` — Some maps had null values (still shown with available data)
- `unavailable` — No series found or team cannot be resolved

### Estimated Market (Form-based Odds)

**Source:** `_estimated_market()` in `backend/app/services/lol_metrics_engine.py`

Alongside statistical averages, the engine now computes a **probabilistic market estimate** for each match based on both teams' recent series win/loss records. This estimate is returned as `estimated_market` in the `compute_match_statistics()` payload.

**Method — Laplace-smoothed relative probability:**

For each team with `series_wins` and `series_losses` over their recent series (sample size = W + L):

```
strength = (wins + 1) / (sample + 2)          # Laplace smoothing
p_a = strength_a / (strength_a + strength_b)   # Relative probability
decimal_odds_a = 1 / p_a
```

Laplace smoothing avoids impossible 0% or 100% probabilities in a 5-series sample.

**Output per team:**
- `probability_pct` — Relative win probability (e.g., 62.5%)
- `decimal_odds` — Fair implied market odds (e.g., 1.60)
- `series_wins`, `series_used` — Context for the estimate

**When unavailable:** If either team has no decided series, `available` is `false` with a descriptive `reason` ("Se requiere al menos una serie decidida por equipo").

**Data notes updated:** The `data_notes.odds` message now reads: "Las cuotas calculadas son una estimación estadística interna y no representan una casa de apuestas."

### Recent Matchups

**Source:** `_recent_matchups()` in `backend/app/services/lol_metrics_engine.py`

The `_team_payload()` response includes `recent_matchups`: the last 3 individual maps (not series aggregates) for each team, sorted by date descending. Each entry contains:

- `date` — Game date
- `game_number` — Map index within the original series
- `opponent` — The opposing team name
- `score` — Per-map result (e.g., `"1-0"` or `"0-1"`)
- `result` — `"win"`, `"loss"`, or `"draw"`
- `duration_seconds` — Game duration for this map
- `team` / `opponent_stats` — Per-side values: `name`, `kills`, `towers`, `inhibitors`

The match detail page renders this data in a `#recent-matchups` section labeled "\u00daltimos mapas". Each card shows the date, map number, opponent logo, per-map score, and side-by-side stat comparisons for kills, towers, and inhibitors.

### Dashboard Preview Odds

**Source:** `backend/app/static/js/app.js` — `oddsHtml()`

Preview odds are now rendered **server-side** in the upcoming matches API response. The `GET /api/lol/matches/upcoming` endpoint loads cached `estimated_market` data for all scheduled matches in two queries (one for the cache table, then batch loads odds), and each match view in the response includes `estimated_market` directly. The dashboard card grid calls `oddsHtml(match, match.estimated_market)` inline during rendering — no separate async fetch, no client-side cache, no loading skeleton.

**Mechanism:**
1. The `/upcoming` endpoint loads `LolMatchStatisticsReadModel` rows for all scheduled matches in a single query and resolves cached statistics via `cached_statistics_from_record()`.
2. Odds are batch-loaded via `_current_odds_by_match()` (2 queries total instead of 2N).
3. `_match_view()` accepts optional `estimated_market` and `odds` parameters, so the upcoming list includes pre-loaded values.
4. The match card renders `estimated_market` directly via `oddsHtml()` in the `renderMatches()` function. No placeholder, no worker pool.

**Rendered output** (when available):

```
<div class="match-odds available estimated-preview">
  <span>T1 <strong>1.60</strong></span>
  <span>Gen.G <strong>2.67</strong></span>
  <small>Cuotas calculadas · 62.5% / 37.5% · 5 series</small>
</div>
```

The match detail page shares the same `estimated_market` data but calls `renderMatchOdds()` for a richer layout with a market-source badge, model description, and external odds reference. The underlying data (decimal odds, probability percentages, series count) is identical.

### Statistics Cache & Precomputation

**Sources:**
- `backend/app/services/lol_metrics_engine.py` — `precompute_upcoming_stats()`, `cached_match_statistics()`, `store_match_statistics()`, `invalidate_statistics_cache()`
- `backend/app/routers/lol_api.py` — `/statistics` and `/upcoming` endpoints now serve cached data
- `backend/app/models_lol.py` — `LolMatchStatisticsReadModel.payload_json` and `coverage_json` are `Optional[dict]` (JSON columns), not strings

Statistics are **cached** in `LolMatchStatisticsReadModel` to avoid recomputing on every request.

**Computation flow:**
1. `precompute_upcoming_stats(session)` — Worker job (every 30 minutes, runs immediately on worker start). For each scheduled match with no valid cached entry, it calls `compute_match_statistics()` and persists the result via `store_match_statistics()`. Returns `{"precomputed": N, "skipped": M, "total_scheduled": total}`.
2. `cached_match_statistics(session, match)` — Reads `LolMatchStatisticsReadModel` and validates the `input_fingerprint` (SHA-256 of match_key, teams, start_time, updated_at). Returns `(payload, coverage, computed_at)` if valid, `None` if stale or missing.
3. `cached_statistics_from_record(cached, match)` — Validates a loaded row without a DB round-trip.
4. `invalidate_statistics_cache(session)` — Deletes all cached rows. Called automatically by `rebuild_series()`, `sync_leaguepedia_schedule()`, and the Oracle's Elixir inbox importer when games change.
5. `store_match_statistics(session, match, payload, coverage)` — Upserts a cache row with the current `input_fingerprint`.

**Cache invalidation triggers:**
- Series rebuild (after Oracle's Elixir import)
- Leaguepedia schedule sync (when matches are inserted or updated)
- Oracle's Elixir inbox import (any new games trigger a series rebuild which clears the cache)

**Serve pattern:**
- `GET /api/lol/matches/{key}/statistics` — Reads cache; returns `{"status":"ready","payload":...,"coverage":...}` if valid, or `{"status":"pending"}` if not yet computed (the frontend JS renders a neutral message rather than an error).
- `GET /api/lol/matches/upcoming` — Batch-loads cache rows for all scheduled matches and includes `estimated_market` directly in each match view.
- Dashboard JS (`app.js`) renders `match.estimated_market` inline — no separate fetch for preview odds.

## Competition Classification

**Source:** `backend/app/routers/lol_api.py`

The competition classifier maps Leaguepedia league/tournament strings to canonical codes.
For the 2026 season, the former **LTA** (League of The Americas) has been replaced by its two constituent sub-leagues: **LCS** (LTA North) and **CBLOL** (LTA South).

| Code | Competition | Detection |
|------|-------------|-----------|
| `LCK` | League of Legends Champions Korea | League starts with `LCK` (excluding `LCK CL`) |
| `LPL` | League of Legends Pro League | League starts with `LPL` |
| `LEC` | League of Legends EMEA Championship | League starts with `LEC` |
| `LCS` | League Championship Series | League starts with `LCS`, or league text matches `^LTA NORTH(?:/\|$)` |
| `CBLOL` | Campeonato Brasileiro de League of Legends | League starts with `CBLOL`, or league text matches `^LTA SOUTH(?:/\|$)` |
| `LCP` | League of Legends Championship Pacific | League starts with `LCP` |
| `WORLDS` | World Championship | Contains "World Championship" or "Worlds" |
| `MSI` | Mid-Season Invitational | Contains "Mid-Season Invitational" or "MSI" |
| `FIRST_STAND` | First Stand | Contains "First Stand" |
| `EWC` | Esports World Cup | Contains "Esports World Cup" |
| `KESPA` | KeSPA Cup | Contains "KeSPA Cup" |

Dashboard displays only these 11 competitions. Academy leagues (e.g., `LCK CL`) are excluded.
A bare `LTA` (without North/South qualifier) does not match any competition code and is excluded.

## Official 2026 Competition Rosters

**Source:** `OFFICIAL_COMPETITION_ROSTERS_2026` in `backend/app/routers/lol_api.py`

As of the 2026 season, the API maintains an authoritative roster catalog for every tracked competition. Each roster entry includes a `status` field and an `official_source_url` linking to the lolesports.com tournament page or official announcement.

### Active Rosters (published)

| Code | Competition | Teams | Official Source |
|------|-------------|-------|-----------------|
| `LCK` | LCK | Gen.G Esports, T1, NONGSHIM RED FORCE, DN SOOPers, HANJIN BRION, Hanwha Life Esports, Dplus KIA, kt Rolster, BNK FEARX, KIWOOM DRX | [LCK 2026 Overview](https://lolesports.com/en-US/tournament/115548106590082745/overview) |
| `LPL` | LPL | Anyone's Legend, BILIBILI GAMING, Invictus Gaming, Beijing JDG Esports, Shenzhen NINJAS IN PYJAMAS, Xi'an Team WE, TOP ESPORTS, WeiboGaming, EDWARD GAMING, LGD GAMING, Suzhou LNG Esports, Oh My God, THUNDER TALK GAMING, Ultra Prime | [LPL 2026 Overview](https://lolesports.com/en-US/tournament/115615907996665826/overview) |
| `LEC` | LEC | Team Heretics, Natus Vincere, Team Vitality, Shifters, GIANTX, SK Gaming, Movistar KOI, Fnatic, Karmine Corp, G2 Esports | [LEC 2026 Overview](https://lolesports.com/en-US/tournament/115548681802226458/overview) |
| `LCS` | LCS | Sentinels, Cloud9 Kia, Dignitas, Disguised, FlyQuest, LYON, Shopify Rebellion, Team Liquid Alienware | [LCS 2026 Address](https://lolesports.com/news/lcs-2026-address) |
| `CBLOL` | CBLOL | Fluxo W7M, FURIA, LEVIATÁN, LOS, LOUD, paiN Gaming, RED Kalunga, Vivo Keyd Stars | [CBLOL 2026 Overview](https://lolesports.com/en-US/tournament/115565518151768348/overview) |
| `LCP` | LCP | CTBC Flying Oyster, DetonatioN FocusMe, Relove Deep Cross Gaming, GAM Esports, Ground Zero Gaming, MVK Esports, Fukuoka SoftBank HAWKS gaming, Team Secret Whales | [LCP 2026 Overview](https://lolesports.com/en-US/tournament/115570728597462574/overview) |
| `MSI` | MSI 2026 | BILIBILI GAMING, TOP ESPORTS, Hanwha Life Esports, T1, G2 Esports, Karmine Corp, LYON, Team Liquid Alienware, Team Secret Whales, Relove Deep Cross Gaming, FURIA | [MSI News](https://lolesports.com/en-US/news/msi-) |
| `FIRST_STAND` | First Stand | BILIBILI GAMING, Beijing JDG Esports, Gen.G Esports, BNK FEARX, G2 Esports, LYON, Team Secret Whales, LOUD | [First Stand League](https://lolesports.com/en-US/leagues/first_stand) |
| `EWC` | Esports World Cup 2026 | AG.AL, BILIBILI GAMING, Dplus KIA, FURIA, G2 Esports, GAM Esports, Gen.G Esports, Hanwha Life Esports, Beijing JDG Esports, Karmine Corp, LYON, MIBR.LOS, Movistar KOI, Sentinels, T1, Team Secret | [EWC LoL Competition](https://esportsworldcup.com/en/competitions/league-of-legends) |

All of the above carry `"status": "official"` — the team list is confirmed by Riot Games.

### Pending Rosters (not yet published)

| Code | Competition | Status | Source |
|------|-------------|--------|--------|
| `WORLDS` | World Championship 2026 | `not_published` | [MSI and Worlds Updates](https://lolesports.com/en-US/news/msi-and-worlds-updates) |

Worlds has no qualified teams published yet. The dashboard displays "Los participantes oficiales todavía no fueron publicados" for this competition.

### How rosters are surfaced

The `_competition_summary()` function in `lol_api.py` merges official rosters with data from the calendar:

- For the **2026 season**, teams are sourced directly from `OFFICIAL_COMPETITION_ROSTERS_2026`, overriding any teams discovered by scanning match events.
- For **other years**, teams are derived from `LolMatchEvent` records (status `calendar_derived`).
- Each competition response includes `roster_status` (`official`, `calendar_derived`, or `not_published`) and `official_source_url` when an official source is available.
- The dashboard UI renders a green "Lista oficial" badge for `official` rosters and a gray "Pendiente" badge for `not_published`.

## Team Name Resolution

**Source:** `backend/app/services/lol_team_aliases.py`

Team names from different sources (Leaguepedia, Oracle's Elixir, CSV odds) must be unified:

1. **Exact match** against `LolTeamAlias.alias`
2. **Normalized match** — Unicode NFKD decomposition, lowercase, remove `esports`, `gaming`, `team`, `club`, `lol` suffixes
3. **League-scoped** — Optional filtering by `league_slug` for ambiguous names

Supports temporal aliases via `active_from`/`active_to` date ranges.

## League Catalog

**Source:** `backend/app/services/lol_league_catalog.py`

Defines 9 active leagues (`ACTIVE_LEAGUES`) and 7 legacy leagues (`LEGACY_LEAGUES`) with names, regions, and known aliases. Seeded into `LolLeague` and `LolLeagueAlias` tables on first run.
