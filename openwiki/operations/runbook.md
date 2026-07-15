# Operations

## Docker Compose

### Starting

```bash
cp .env.example .env
# Edit .env with your settings
docker compose up -d --build
```

### Checking status

```bash
docker compose ps                    # All three services
curl http://localhost:8090/health    # Web app
docker compose logs -f pirapire_app  # App logs
docker compose logs -f pirapire_worker  # Worker logs
```

### Stopping / restarting

```bash
docker compose stop pirapire_app        # Stop web only
docker compose restart pirapire_app     # Restart web only
docker compose down                     # Stop all, preserve data/
docker compose up -d --build pirapire_app  # Rebuild after code changes
```

### Port change

Edit `PIRAPIRE_PORT` in `.env`, then `docker compose up -d`.

## Worker scheduler

The worker container runs `backend/app/worker_main.py` with APScheduler. All jobs use `coalesce=True` and `max_instances=1`.

| Job | Interval | Function | Notes |
|-----|----------|----------|-------|
| Aposta sync | 12 min | `run_aposta_sync()` | Imports odds from `aposta_import_dir` |
| Historical ingestion | 4 hours | `run_historical_ingestion()` | Fetches football match data from external APIs |
| Fresh football | 30 min | `run_fresh_football()` | SofaScore fallback for recent matches |
| Descriptive stats | 4 hours | `run_descriptive_stats()` | Full rebuild of read-model statistics |
| Event refresh | 2 min | `run_event_refresh()` | Lifecycle states + refresh queue (up to 5 tasks) |
| WC squads | 24 hours | `run_wc_squad_sync()` | World Cup squad data |

### Viewing worker logs

```bash
docker compose logs -f pirapire_worker
```

Look for log lines like:
- `Aposta: N odds` — successful sync
- `Historical ingestion: ...` — ingestion results
- `Fresh football: status=... teams=...` — fresh data status
- `Lifecycle states: {...}` — event state distribution
- `Event refresh: processed N tasks` — refresh queue processing

## Database

### Location

`./data/pirapire.db` (SQLite, WAL journal mode)

### Backup

```bash
mkdir -p backups
cp data/pirapire.db "backups/pirapire_$(date +%Y%m%d_%H%M%S).db"
```

### Restore

```bash
docker compose down
cp backups/pirapire_YYYYMMDD_HHMMSS.db data/pirapire.db
docker compose up -d
```

### Inspect

```bash
sqlite3 data/pirapire.db ".tables"
sqlite3 data/pirapire.db "SELECT count(*) FROM apostaevent;"
sqlite3 data/pirapire.db "SELECT local_event_state, count(*) FROM apostaevent GROUP BY 1;"
```

## Updates

```bash
cd /path/to/pirapire
git pull
docker compose up -d --build pirapire_app
```

Data in `./data` is preserved across updates. Worker container uses the same image, so it picks up changes automatically.

## Manual operations via UI

| Action | URL |
|--------|-----|
| Import CSV odds | `/imports/ui` |
| Sync football data | `/sources/ui` → "Actualizar Fútbol" |
| Sync LoL data | `/sources/ui` → "Actualizar LoL" |
| Recalculate recommendations | `/` → "Recalcular recomendaciones" |
| View recommendations | `/recommendations/ui` |
| Manage integrations | `/settings/ui` |

## Troubleshooting

### Port 8090 occupied
Change `PIRAPIRE_PORT` in `.env` and restart.

### `/health` not responding
```bash
docker compose logs pirapire_app
```
Check for startup errors (missing .env, DB permission issues, port conflicts).

### Football returns `partial` or 429
Rate limit from football-data.org free tier. Increase `FOOTBALL_DATA_REQUEST_DELAY_SECONDS` or reduce `FOOTBALL_DATA_MAX_COMPETITIONS_PER_RUN` in `.env`.

### No recommendations
1. Verify odds are imported: check `/imports/ui`
2. Verify sports data is synced: check `/sources/ui`
3. Click "Recalcular recomendaciones" on dashboard or recommendations page

### Worker not processing
```bash
docker compose logs pirapire_worker
```
Check for Python import errors, DB lock issues, or APScheduler misconfiguration.

### Browser worker
The browser worker is optional. If it's not running:
- Fresh football will skip SofaScore fallback
- Aposta browser fetch won't work
- Check `docker compose ps pirapire_browser`

### Database locked
If you see "database is locked" errors, ensure both containers have `check_same_thread=False` (set in `database.py`). WAL mode should prevent most lock contention. If persistent, restart both containers:
```bash
docker compose restart pirapire_app pirapire_worker
```

## Reverse proxy (optional)

Copy `compose.override.example.yml` to `compose.override.yml`, uncomment and configure:
- Attach to external network (e.g., Traefik `web` network)
- Remove port publishing (`ports: []`)
- Add proxy labels

## Environment variables reference

See `.env.example` and `backend/app/config.py` for all available settings. Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `PIRAPIRE_PORT` | `8090` | Host port |
| `APP_TIMEZONE` | `America/Argentina/Buenos_Aires` | Display timezone |
| `FOOTBALL_DATA_API_KEY` | (empty) | football-data.org auth |
| `API_FOOTBALL_API_KEY` | (empty) | API-Football auth |
| `RECOMMENDER_DEFAULT_MODE` | `probability` | Default ranking mode |
