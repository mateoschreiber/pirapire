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

| Metric | Description | Formula |
|--------|-------------|---------|
| Towers % | Tower control share | `T_t / (T_t + T_o)` |
| Inhibitors % | Inhibitor control share | `I_t / (I_t + I_o)` |
| Kills % | Kill share | `K_t / (K_t + K_o)` |
| Deaths % | Death share | `D_t / (D_t + D_o)` |
| Dragons % | Dragon control share | `Dg_t / (Dg_t + Dg_o)` |
| Barons % | Baron control share | `B_t / (B_t + B_o)` |
| End Gold % | Gold share at game end | `G_t / (G_t + G_o)` |
| Avg Map Duration | Average game length | Mean of `game_length_seconds` |
| Avg Series Duration | Average total series length | Sum of game durations per series |

### Player Metrics

Computed per player from the same recent series:

| Metric | Description |
|--------|-------------|
| Kills % | Player kills vs match total |
| Deaths % | Player deaths vs match total |
| End Gold % | Player gold share |
| Solo Kills Per Map | Average solo kills |
| CS Per Map | Average creep score |
| CS % | Player CS vs match total |

### Coverage Labels

- `complete` — All expected maps have valid data
- `partial` — Some maps had null values (still shown with available data)
- `unavailable` — No series found or team cannot be resolved

### Cache

`LolMatchStatisticsReadModel` stores precomputed stats with an `input_fingerprint` for cache invalidation. Stats are recomputed when the underlying source data changes.

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
