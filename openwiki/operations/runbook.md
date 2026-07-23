# Operations / Runbook

## Deployment

### Docker Compose

```bash
# Start both services
docker compose up -d --build

# View logs
docker compose logs -f pirapire_app
docker compose logs -f pirapire_worker

# Restart worker (e.g., after config change)
docker compose restart pirapire_worker

# Stop everything
docker compose down
```

**Source:** `/docker-compose.yml`, `/backend/Dockerfile`

### Health Check

The app container has a Docker health check:
```bash
curl -f http://localhost:8090/health
# → {"status": "ok"}
```

The worker writes a heartbeat every 60 seconds to the `WorkerHeartbeat` table.

### First-Run Setup

```bash
cp .env.example .env
mkdir -p data/imports/lol_odds/inbox data/imports/lol_odds/processed data/imports/oracles/inbox data/imports/oracles/processed data/imports/oracles/errors logs
docker compose up -d --build
```

The database is created automatically on first startup via `init_db()`.

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `Pirapire` | App title |
| `APP_ENV` | `local` | Environment label |
| `APP_TIMEZONE` | `America/Asuncion` | Display timezone |
| `APP_PUBLIC_URL` | `""` | Public URL for external links |
| `DATABASE_URL` | `sqlite:////app/data/pirapire.db` | SQLite path |
| `LOG_LEVEL` | `INFO` | Logging level |
| `ADMIN_TOKEN` | `""` | Token for admin API operations |
| `PIRAPIRE_PORT` | `8090` | Host HTTP port |
| `DATADRAGON_BASE_URL` | `https://ddragon.leagueoflegends.com` | Data Dragon API base |
| `DATADRAGON_LOCALE` | `es_MX` | Champion data locale |
| `LEAGUEPEDIA_USER_AGENT` | `PirapireLocal/1.0` | HTTP User-Agent for Leaguepedia |
| `LEAGUEPEDIA_SYNC_ENABLED` | `true` | Enable schedule sync |
| `LGPD_IMPORT_LOOKBACK_DAYS` | `21` | Lookback for schedule sync |
| `LGPD_IMPORT_LOOKAHEAD_DAYS` | `14` | Lookahead for schedule sync |
| `LOL_HISTORY_ENABLED` | `true` | Enable history import |
| `LOL_HISTORY_START_YEAR` | `2021` | Earliest year to import |
| `LOL_HISTORY_END_YEAR` | `auto` | `auto` = current year |
| `LOL_HISTORY_ACTIVE_LEAGUES` | `LCK,LPL,LEC,LCS,...` | Tracked leagues |
| `LOL_HISTORY_INCLUDE_LEGACY` | `true` | Include legacy leagues |
| `LOL_HISTORY_IMPORT_DIR` | `/app/data/imports/oracles` | Import directory |
| `LOL_HISTORY_ALLOW_DOWNLOAD` | `false` | Allow auto-download |
| `LOL_HISTORY_REMOTE_MAX_MB` | `100` | Max MB for remote Oracle CSV download |
| `LOL_HISTORY_MIN_GAMES_TEAM` | `8` | Min games for model confidence (team) |
| `LOL_HISTORY_MIN_GAMES_PLAYER` | `5` | Min games for model confidence (player) |
| `LOL_HISTORY_RECENT_GAMES_WINDOW` | `20` | Window size for recent games |
| `LOL_ODDS_IMPORT_DIR` | `/app/data/imports/lol_odds` | Odds CSV import directory |
| `LOL_SCHEDULE_INTERVAL_MINUTES` | `30` | Leaguepedia sync interval |
| `LOL_HISTORY_INTERVAL_MINUTES` | `60` | OE history import interval (legacy, retained for local inbox and existing deployments) |
| `LOL_HISTORY_REMOTE_POLL_MINUTES` | `60` | Remote Oracle CSV poll interval (controls `sync_remote_oracles` worker job) |
| `DATADRAGON_INTERVAL_MINUTES` | `1440` | Data Dragon sync interval |
| `TEAM_LOGO_SYNC_INTERVAL_MINUTES` | `1440` | Official team logo sync interval |
| `LOL_IMPORT_POLL_INTERVAL_MINUTES` | `30` | CSV import poll interval |

## Data Directories

Pirapire mounts `./data` to `/app/data` inside containers:

```
data/
├── imports/
│   ├── lol_odds/
│   │   ├── inbox/       → Worker polls for new odds CSVs (every 5 min)
│   │   └── processed/   → Successfully imported files move here
│   └── oracles/
│       ├── inbox/       → Worker polls for new OE CSVs (every 30 min); also holds web uploads under inbox/uploads/
│       ├── processed/   → Successfully imported files move here
│       └── errors/      → Failed imports move here
└── pirapire.db          → SQLite database (auto-created)
```

## Admin Operations

### Upload Oracle's Elixir CSV

1. Navigate to `/sources` → **Archivos** tab
2. Enter admin token
3. Select CSV file (max 100 MB)
4. Preview first 20 rows
5. Save to import

Or via API:
```bash
curl -X POST http://localhost:8090/api/sources/oracles/upload \
  -H "X-Admin-Token: your-token" \
  -F "file=@oracles_elixir_data.csv"
```

### Import Odds CSV

Place CSV files in `data/imports/lol_odds/inbox/`. The worker picks them up within 5 minutes.

## Troubleshooting

| Symptom | Likely Cause | Check |
|---------|-------------|-------|
| Dashboard shows no matches | Leaguepedia sync failed or not yet run | Worker logs: `docker compose logs pirapire_worker` |
| Odds not showing | CSV not in inbox or import failed | Check `data/imports/lol_odds/errors/` |
| "No hay encuentros" | Filter active or window too narrow | Check competition filter on dashboard |
| Statistics show "N/D" | No Oracle's Elixir data imported | Check `data/imports/oracles/inbox/` and `/api/imports` |
| Health check fails | Database locked or startup not complete | Check database file permissions |
| Statistics stale | Worker precompute not scheduled | `job_precompute_stats` is defined but not on the default scheduler |

## Upgrading

```bash
git pull origin main
docker compose up -d --build
```

The application handles schema updates idempotently via `migrations.py`. No manual migration steps needed.
