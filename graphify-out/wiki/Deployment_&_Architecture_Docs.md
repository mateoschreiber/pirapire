# Deployment & Architecture Docs

> 29 nodes

## Key Concepts

- **Pirapire — LoL Esports Analytics Platform** (5 connections) — `openwiki/quickstart.md`
- **APScheduler Background Worker** (5 connections) — `openwiki/architecture/overview.md`
- **Statistics Engine (on-demand)** (5 connections) — `openwiki/domain/lol-metrics.md`
- **LolSeries model** (4 connections) — `openwiki/domain/lol-metrics.md`
- **Estimated Market (Form-based Odds)** (4 connections) — `openwiki/domain/lol-metrics.md`
- **Two-Container Deployment** (3 connections) — `openwiki/architecture/overview.md`
- **Leaguepedia Cargo API** (3 connections) — `openwiki/integrations/overview.md`
- **pirapire_app Docker Service** (3 connections) — `docker-compose.yml`
- **Series Builder Service** (2 connections) — `openwiki/architecture/overview.md`
- **LolGameHistory model** (2 connections) — `openwiki/domain/lol-metrics.md`
- **Oracle's Elixir CSV** (2 connections) — `openwiki/integrations/overview.md`
- **Manual Odds CSV** (2 connections) — `openwiki/integrations/overview.md`
- **Leaguepedia Schedule Sync** (2 connections) — `openwiki/workflows/data-pipeline.md`
- **Odds CSV Import Workflow** (2 connections) — `openwiki/workflows/data-pipeline.md`
- **Docker Compose Deployment Procedure** (2 connections) — `openwiki/operations/runbook.md`
- **Phase 1 Refactor (commit b8e1b04)** (1 connections) — `openwiki/architecture/overview.md`
- **SQLite Concurrent Access** (1 connections) — `openwiki/architecture/overview.md`
- **Sources Admin API** (1 connections) — `openwiki/architecture/overview.md`
- **LoL Metrics Engine Service** (1 connections) — `openwiki/architecture/overview.md`
- **Team Logo Sync Service** (1 connections) — `openwiki/architecture/overview.md`
- **LolMatchEvent model** (1 connections) — `openwiki/domain/lol-metrics.md`
- **LolOddsSnapshot model** (1 connections) — `openwiki/domain/lol-metrics.md`
- **Laplace Smoothing** (1 connections) — `openwiki/domain/lol-metrics.md`
- **Dashboard Preview Odds** (1 connections) — `openwiki/domain/lol-metrics.md`
- **Recent Matchups Feature** (1 connections) — `openwiki/domain/lol-metrics.md`
- *... and 4 more nodes in this community*

## Relationships

- No strong cross-community connections detected

## Source Files

- `docker-compose.yml`
- `openwiki/architecture/overview.md`
- `openwiki/domain/lol-metrics.md`
- `openwiki/integrations/overview.md`
- `openwiki/operations/runbook.md`
- `openwiki/quickstart.md`
- `openwiki/workflows/data-pipeline.md`

## Audit Trail

- EXTRACTED: 16 (27%)
- INFERRED: 44 (73%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*