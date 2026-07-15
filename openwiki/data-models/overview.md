# Data Models

All models use SQLModel (SQLAlchemy + Pydantic). The database is a single SQLite file with WAL journal mode. Schema is created via `SQLModel.metadata.create_all()` on startup, plus runtime migrations in `database.py`.

## Model files

| File | Tables | Purpose |
|------|--------|---------|
| `models.py` | `Sport`, `Team`, `Match`, `OddsSnapshot`, `Prediction` | Core/legacy entities |
| `models_aposta.py` | `ApostaSyncRun`, `ApostaEvent`, `RefreshQueue`, `ApostaMarket`, `ApostaSelection`, `CaptureSnapshot`, `CanonicalMarket`, `CanonicalOutcome` | Aposta.LA betting odds pipeline, snapshots, canonical identity |
| `models_football.py` | `FootballCompetition`, `FootballTeam`, `FootballStanding`, `FootballMatch`, `FootballPlayer`, `FootballEntityMetadata` | Football historical data |
| `models_lol.py` | `LolPatch`, `LolChampion`, `LolLeague`, `LolTeamAlias`, `LolLeagueAlias`, `LolGameHistory`, `LolSeries` | LoL competitive data |
| `models_imports.py` | `ManualImportBatch`, `ManualImportError`, `ImportedOdds` | CSV import tracking and normalized odds |
| `models_markets.py` | `MarketCatalog` | Standardized market taxonomy with ES/EN aliases |
| `models_recommendations.py` | `BetRecommendation`, `ComboRecommendation`, `ComboRecommendationLeg`, `RecommendationRun` | Recommendation engine output |
| `models_sources.py` | `DataSource`, `SourceCapability` | External source registry |
| `models_history.py` | `PredictionHistory`, `ComboHistory`, `ComboLegHistory` | Manual bet settlement tracking (won/lost/void/pending) |

## Key entities

### ApostaEvent (`models_aposta.py`)

Central entity connecting odds imports to the rest of the system. Key fields:

- `event_key`: canonical identity string (`evt_<sha256>`), derived from `source + source_event_id` (native) or `source + sport + teams + competition + kickoff` (derived). Used as foreign key throughout the system
- `sport`: `"football"` or `"lol"`
- `team_a`, `team_b`, `competition`: extracted from Aposta odds
- `kickoff_utc`: parsed kickoff time
- `current_snapshot_id`: FK to `CaptureSnapshot`
- `local_event_state`: lifecycle state (Phase 4D1) — `scheduled`, `live`, `finished`, `stale`, etc.
- `source_event_id`: Aposta.LA internal event ID

### ImportedOdds (`models_imports.py`)

Normalized odds rows imported from Aposta.LA CSVs. Each row represents one selection (outcome) within a market:

- `event_key`: FK to `ApostaEvent`
- `market_code`, `market_text`, `line`: market identification
- `selection`, `odds_decimal`: the bet outcome and its decimal odds
- `is_current`: soft-delete flag — only current odds are active
- `canonical_market_id`: FK to `MarketCatalog`

### FootballMatch (`models_football.py`)

Historical football match data from external APIs:

- `source_name`, `source_external_id`: source tracking
- `home_team_id`, `away_team_id`: FK to `FootballTeam`
- `competition_id`: FK to `FootballCompetition`
- `match_date`, `status`, `matchday`
- Score fields: `home_score`, `away_score`, `half_time_home`, `half_time_away`
- `source_rank`, `fallback_used`: data quality tracking

### RefreshQueue (`models_aposta.py`)

Phase 4D1 coalesced refresh queue:

- `event_key`: unique per event (coalesced — new syncs overwrite same row)
- `reason`: `added`, `kickoff_changed`, `participants_changed`, `markets_changed`
- `locked_by`, `locked_at`: instance-level locking for worker task claims

### MarketCatalog (`models_markets.py`)

Standardized market taxonomy:

- `code`: internal code (e.g., `match_winner`, `total_goals_over_under`)
- `name_es`, `name_en`: bilingual names
- `category`: grouping (e.g., `resultado`, `goles`, `mapas`)
- `sport`: `football` or `lol`

## Relationships map

```
ApostaSyncRun 1──N ImportedOdds N──1 ApostaEvent
                                             │
ApostaEvent 1──N ApostaMarket 1──N ApostaSelection
                                             │
ApostaEvent 1──1 RefreshQueue                │
                                             │
FootballMatch N──1 FootballTeam (home/away)  │
FootballMatch N──1 FootballCompetition       │
                                             │
ImportedOdds N──1 MarketCatalog              │
                                             │
RecommendationRun 1──N BetRecommendation     │
RecommendationRun 1──N ComboRecommendation 1──N ComboRecommendationLeg
```

## Migrations

Runtime migrations run in `database.py:_run_migrations()`:
1. `aposta_snapshot.run_migrations()` — canonical identity backfill
2. `integration_migrations.run_migrations()` — integration schema updates
3. `aposta_snapshot.backfill_canonical_identity()` — event_key population

Migrations are additive and idempotent — they check for existing state before applying changes.

## WAL journal (Phase 4D2)

SQLite uses WAL (Write-Ahead Logging) journal mode for better concurrent read/write performance. Applied via `integration_migrations.py`. The worker container and web container share the same DB file; WAL mode reduces lock contention between the scheduler (writes) and the web UI (reads).
