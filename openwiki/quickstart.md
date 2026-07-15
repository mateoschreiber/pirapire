# Pirapire — OpenWiki

Sistema analítico de apuestas deportivas (fútbol y League of Legends). Corre en un contenedor Docker liviano, importa cuotas de Aposta.LA, sincroniza datos deportivos de múltiples APIs, estima probabilidades por mercado y recomienda apuestas individuales y combinadas.

> **Advertencia:** Pirapire es una herramienta **analítica**. No coloca apuestas, no inicia sesión en casas de apuestas y no automatiza apuestas reales.

## Tech stack

- **API:** FastAPI 0.139 + Uvicorn (port 8000 interno → host `${PIRAPIRE_PORT}`)
- **ORM:** SQLModel / SQLAlchemy + SQLite (`data/pirapire.db`)
- **UI:** Jinja2 templates + vanilla JS + CSS
- **Worker:** APScheduler (background, same image, separate container)
- **Browser:** Playwright-based browser worker (separate container, optional)
- **Deploy:** Docker Compose (3 services: `pirapire_app`, `pirapire_worker`, `pirapire_browser`)

## Quick navigation

| Section | Description |
|---------|-------------|
| [Architecture](architecture/overview.md) | System design, Docker services, tech stack, routing, worker scheduler |
| [Data Pipeline](workflows/data-pipeline.md) | Aposta sync → historical ingestion → fresh football → event lifecycle → refresh → descriptive stats → recommendations |
| [Data Models](data-models/overview.md) | SQLite schema: football, LoL, apostas, imports, markets, recommendations |
| [Integrations](integrations/overview.md) | External APIs, source registry, integration settings, browser worker, credential management |
| [Operations](operations/runbook.md) | Docker operations, backups, updates, worker jobs, troubleshooting |
| [Testing](testing/overview.md) | Test structure, fixtures, categories, running tests |

## Repository map

```
pirapire/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, lifespan, router mounts
│   │   ├── worker_main.py       # Background scheduler (APScheduler)
│   │   ├── config.py            # All settings via pydantic-settings / env vars
│   │   ├── database.py          # SQLModel engine, init_db(), migrations
│   │   ├── models*.py           # SQLModel table definitions (7 model files)
│   │   ├── routers/             # 16 API routers (HTML + JSON endpoints)
│   │   ├── services/            # ~45 service modules (business logic)
│   │   ├── sources/             # External API connectors (football/ + lol/)
│   │   ├── templates/           # 18 Jinja2 HTML templates
│   │   └── static/              # CSS and vanilla JS
│   ├── tests/                   # 35 test files, conftest.py with temp SQLite
│   ├── Dockerfile               # Python 3.12-slim image
│   └── requirements.txt         # Python dependencies
├── browser-worker/               # Playwright-based browser automation service
│   ├── browser_worker.py        # FastAPI app with /render endpoint
│   └── Dockerfile
├── docs/                        # Phase/recovery documentation (24 markdown files)
├── scripts/sync_pirapire.sh     # Remote sync helper
├── docker-compose.yml           # 3-service deployment
├── compose.override.example.yml # Optional reverse-proxy integration
├── README.md, INSTALL.md, DEPLOYMENT.md, SECURITY.md
└── data/                        # SQLite database + imports (gitignored)
```

## Entry points

| Entry point | File | Purpose |
|-------------|------|---------|
| Web API + UI | `backend/app/main.py` | FastAPI app, all routes, templates, static files |
| Background worker | `backend/app/worker_main.py` | APScheduler running 6 periodic jobs |
| Browser worker | `browser-worker/browser_worker.py` | Playwright rendering for SofaScore/Aposta.LA scraping |

## Key URLs (local)

- Dashboard: `http://localhost:8090/`
- Recommendations: `http://localhost:8090/recommendations/ui`
- Events: events detail pages, Swagger: `http://localhost:8090/docs`, Health: `http://localhost:8090/health`
- See [operations runbook](operations/runbook.md) for all UI URLs

## Project evolution (recent phases)

The codebase was rebuilt through a structured recovery process. Key recent milestones:

| Phase | Commits | Delivery |
|-------|---------|----------|
| 4D2 | `90c1e69`–`9eac3f5` | WAL journal mode, dashboard query optimization, compound indexes |
| 4D1 | `66fde6e` | Event lifecycle states, reconciliation diff, coalesced refresh queue |
| 4C | `9c94887` | Descriptive statistics read-model, read-only API |
| 4B4 | `00625ad` | Fresh football window via football-data + SofaScore browser fallback |
| 4B3 | `06bc462` | LoL map+player facts for last-5 series, football stale eligibility fix |
| 4B2 | `f1dae93` | Freshness marking, series completion, browser probe fallback |
| 4B1 | `0c89bb0` | Real bounded historical ingestion for active participants, API-Football source |
| 4B0 | `58442ee` | Bounded ingestion gate, historical_ingestion.py |
| 3 | `a8e18b4` | Canonical markets, safe no-vig computation |
| 2 | `dde6bac` | Stable event identity, canonical event_key, snapshot activation idempotency |

Detailed phase docs: `docs/phase*.md` and `docs/recovery-*.md`.

## Backlog

- **Frontend JS / template details** — 18 Jinja2 templates + `app.js` with vanilla JS. Self-documenting; deferred until UI modernization.
- **LoL historical competitive data deep dive** — Oracle's Elixir / Leaguepedia import flows. Partially covered in integrations and workflows.
- **Feature engineering** — `services/features/` (football_features.py, lol_features.py). Deferred until features are actively used in recommendations.
- **Browser / SofaScore scraping detail** — Covered at overview level in integrations; detailed flow docs deferred.

---

*Last updated: see [.last-update.json](.last-update.json)*
