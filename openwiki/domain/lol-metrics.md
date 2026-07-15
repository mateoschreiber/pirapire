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
| Towers destroyed | Torretas destruidas · promedio por mapa | Absolute per-map average |
| Inhibitors destroyed | Inhibidores destruidos · promedio por mapa | Absolute per-map average |
| Kills | Asesinatos · promedio por mapa | Absolute per-map average |
| Deaths | Muertes · promedio por mapa | Absolute per-map average |
| Dragons killed | Dragones asesinados · promedio por mapa | Absolute per-map average |
| Barons killed | Barones asesinados · promedio por mapa | Absolute per-map average |
| Total Gold | Oro total · promedio por mapa | Absolute per-map average |
| Avg Map Duration | Duración promedio del mapa | Mean of `game_length_seconds` |
| Avg Series Duration | Duración promedio de la serie | Sum of game durations per series |

Win rate is computed at the series level, not the map level. A series is "decided" when one team wins more maps than the other — tied series (e.g., 1-1 in BO2) are excluded from win-rate computation. The series-level win/loss is determined by comparing map results within each series. See `_team_payload()` in `backend/app/services/lol_metrics_engine.py` for the map-to-series aggregation logic.

### Player Metrics

Computed per player from the same recent series. The engine computes several internal fields, but the **match detail UI displays only these:**

| Metric | UI Column | Value Type |
|--------|-----------|------------|
| Kills | Asesinatos | Absolute total across maps |
| Deaths | Muertes | Absolute total across maps |
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

### Precomputation (Stub)

`precompute_upcoming_stats()` in `lol_metrics_engine.py` is currently a **stub** that returns `{"precomputed": 0, "total_scheduled": 0}` without actually computing or persisting any statistics. It is scheduled in the background worker every 30 minutes (`job_precompute_stats`) but does nothing yet.

A `LolMatchStatisticsReadModel` model exists in `models_lol.py` for future cached statistics storage, but the app-level service does not write to it. (The standalone root-level `/backend/lol_metrics_engine.py` has an older implementation that does write to this model, but it is superseded by the app package version.)

## Competition Classification

**Source:** `backend/app/routers/lol_api.py`

The competition classifier maps Leaguepedia league/tournament strings to canonical codes:

| Code | Competition | Detection |
|------|-------------|-----------|
| `LCK` | League of Legends Champions Korea | League starts with `LCK` (excluding `LCK CL`) |
| `LPL` | League of Legends Pro League | League starts with `LPL` |
| `LEC` | League of Legends EMEA Championship | League starts with `LEC` |
| `LTA` | League of The Americas | League starts with `LTA` |
| `LCP` | League of Legends Championship Pacific | League starts with `LCP` |
| `WORLDS` | World Championship | Contains "World Championship" or "Worlds" |
| `MSI` | Mid-Season Invitational | Contains "Mid-Season Invitational" or "MSI" |
| `FIRST_STAND` | First Stand | Contains "First Stand" |
| `EWC` | Esports World Cup | Contains "Esports World Cup" |

Dashboard displays only these 9 competitions. Academy leagues (e.g., `LCK CL`) are excluded.

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
