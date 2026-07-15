# Integrations

## External API sources

### Football

| Source | Module | Auth | Rank | Free tier |
|--------|--------|------|------|-----------|
| football-data.org v4 | `sources/football/football_data_org.py` | `X-Auth-Token` header | 90 | Yes (rate-limited) |
| API-Football v3 | `sources/football/api_football.py` | `x-apisports-key` header | 88 | Yes (100/day) |
| OpenLigaDB | `sources/football/openligadb.py` | None (public) | 70 | Yes |
| TheSportsDB | `sources/football/thesportsdb.py` | API key (free `123`) | 60 | Yes |
| SofaScore | Browser worker (Playwright) | None (public pages) | — | Yes |

### League of Legends

| Source | Module | Auth | Rank | Purpose |
|--------|--------|------|------|---------|
| Riot API | `sources/lol/riot_api.py` | `X-Riot-Token` header | 80 | Summoner/match data |
| Data Dragon | `sources/lol/datadragon.py` | None (public) | 75 | Static data (champions, items, patches) |
| Leaguepedia | `leaguepedia_sync_enabled` config | None (CargoExport) | — | LoL esports competitive history |
| Oracle's Elixir | CSV import | None (public download) | — | LoL historical competitive data |

## Source registry

**Service:** `backend/app/services/source_registry.py`

Defines which sources are available, their capabilities, and priority/fallback chains. Sources are discovered with `source_rank` — higher rank sources are tried first. If a higher-ranked source fails or returns insufficient data, lower-ranked fallbacks are used. The `fallback_used` flag is set on entities fetched from fallback sources.

## Integration registry

**Service:** `backend/app/services/integration_registry.py`

8 integration providers defined with contracts:

- `secret_fields`: which credential fields are needed
- `test_method`: how to verify connectivity
- `capabilities`: what data the integration provides
- `rate_limit`: documented rate limits
- `data_role`: `primary`, `secondary`, or `fallback`
- `ENV_FALLBACKS`: maps credential fields to env var names

## Integration settings (UI + API)

**Router:** `backend/app/routers/settings_integrations.py` (16K — largest router)

Authenticated admin API at `/api/settings/`:

- **Auth:** password login with CSRF protection, session cookies
- **Credentials:** CRUD for integration credentials, encrypted at rest via Fernet (`secret_provider.py`)
- **Testing:** `POST /api/settings/integrations/{slug}/test` — runs `integration_tester.py` verification
- **Audit:** all credential changes are logged

## Browser worker

**Service:** `browser-worker/browser_worker.py`

A separate FastAPI container running Playwright + Chromium. Exposes endpoints for:

- **`/render`**: renders a URL in a real browser and extracts visible text/JSON data
- **`/render-sofascore`**: specialized SofaScore team page renderer (Phase 4B4)
- **`/health`**: liveness check

**Security:** URL allowlists restrict which hosts can be rendered:
- Aposta.LA: `aposta.la`, `api.aposta.la`, `www.aposta.la`
- TheSportsDB: `www.thesportsdb.com`, `thesportsdb.com`
- SofaScore: `www.sofascore.com`

Only public, CAPTCHA-free pages are accessed. No login, no private endpoints, no CAPTCHA bypass.

**Used by:**
- `backend/app/services/browser_fallback.py` — renders TheSportsDB team pages when API is unavailable
- `backend/app/services/fresh_football.py` — SofaScore team event pages for recent match data

## Credential management

**Service:** `backend/app/services/secret_provider.py`

- Uses `cryptography.fernet` for symmetric encryption
- Master key stored in a key file (`INTEGRATION_MASTER_KEY_PATH`)
- Session key for settings UI authentication
- Credentials are never logged or exposed in API responses
- `ensure_runtime_secrets()` called during `init_db()` to set up key files

## HTTP client

**Service:** `backend/app/services/http_client.py`

Shared httpx client with:
- Configurable connect/read/write/pool timeouts
- Manual request pacing (configurable delays between requests)
- In-memory caching with TTL (configurable per source)
- 429 retry-after header honoring
- Budget exhaustion tracking (max entities per run)
