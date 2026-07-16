# Pirapire

Analytics platform for professional League of Legends matches. Displays upcoming matches with odds and computes competitive statistics from historical data (Oracle's Elixir, Leaguepedia).

## Quick Start

```bash
git clone https://github.com/mateoschreiber/pirapire.git
cd pirapire
cp .env.example .env
docker compose up -d --build
```

Open `http://localhost:8090`.

## Requirements

- Docker 24+
- Docker Compose v2
- 2 GB RAM, 1 GB disk

## Environment

| Variable | Default | Description |
|---|---|---|
| `PIRAPIRE_PORT` | `8090` | HTTP port |
| `DATABASE_URL` | `sqlite:////app/data/pirapire.db` | SQLite path |
| `APP_TIMEZONE` | `America/Asuncion` | Display timezone |
| `LOL_ODDS_IMPORT_DIR` | `/app/data/imports/lol_odds` | Odds CSV import path |
| `LOL_HISTORY_IMPORT_DIR` | `/app/data/imports/oracles` | Oracle's Elixir CSV import path |
| `LOL_HISTORY_ACTIVE_LEAGUES` | `LCK,LPL,LEC,LCS,...` | Leagues to track |

Full reference in `.env.example`.

## Data Sources

| Source | Purpose |
|---|---|
| [Oracle's Elixir](https://oracleselixir.com/tools/downloads) | Historical competitive match data (CSV import) |
| [Leaguepedia Cargo](https://lol.fandom.com/wiki/Special:CargoExport) | Upcoming schedule, teams, players |
| [Data Dragon](https://developer.riotgames.com/docs/lol) | Static champion/version metadata |
| Manual CSV | General winner odds per match |

## API Endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | Health check |
| `GET` | `/` | Dashboard (upcoming 48h LoL matches) |
| `GET` | `/lol/matches/{match_key}` | Match detail page |
| `GET` | `/api/lol/matches/upcoming?hours=48` | JSON upcoming matches with odds |
| `GET` | `/api/lol/matches/{match_key}` | JSON match info |
| `GET` | `/api/lol/matches/{match_key}/statistics` | Cached statistics payload |

## Odds CSV Format

Place CSV files in the configured `LOL_ODDS_IMPORT_DIR`:

```csv
match_key,team_name,decimal_odds,provider,captured_at
LCK_2025_T1_GEN,T1,1.85,manual,2025-06-01T12:00:00Z
LCK_2025_T1_GEN,Gen.G,1.95,manual,2025-06-01T12:00:00Z
```

Rules: `decimal_odds > 1.0`, exactly 2 teams per match, `captured_at` not in the future.

## Statistics Model

Match detail computes team and player metrics from the last 10 completed series per team (strictly before the target match kickoff):

**Team metrics:** towers %, inhibitors %, kills %, deaths %, dragons %, barons %, end gold %, avg map duration, avg series duration.

**Player metrics:** kills %, deaths %, end gold %, solo kills %, CS % — shown for all players that appeared in the window.

Coverage labels: complete, partial, or N/D when denominator is zero.

## Architecture

```
pirapire/
├── backend/
│   ├── app/
│   │   ├── main.py              FastAPI entry point
│   │   ├── config.py            Pydantic Settings (.env)
│   │   ├── database.py          SQLModel + SQLite engine
│   │   ├── models_lol.py        All LoL ORM models
│   │   ├── routers/
│   │   │   ├── health.py        GET /health
│   │   │   ├── pages.py         HTML templates
│   │   │   └── lol_api.py       JSON API
│   │   ├── services/
│   │   │   ├── lol_metrics_engine.py
│   │   │   ├── lol_team_aliases.py
│   │   │   ├── lol_league_catalog.py
│   │   │   ├── imports/
│   │   │   │   ├── oracles_elixir_importer.py
│   │   │   └── sync/lol_sync.py
│   │   ├── sources/lol/datadragon.py
│   │   ├── templates/           Jinja2 templates
│   │   └── static/              CSS + JS
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml
├── .env.example
```

## Development

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
```

Run tests:

```bash
pytest -q
ruff check app tests
```

## License

MIT
