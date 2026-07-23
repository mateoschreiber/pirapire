# Database & Migrations

> 30 nodes

## Key Concepts

- **main.py** (14 connections) — `backend/app/main.py`
- **database.py** (11 connections) — `backend/app/database.py`
- **migrations.py** (7 connections) — `backend/app/migrations.py`
- **upgrade()** (7 connections) — `backend/app/migrations.py`
- **init_db()** (6 connections) — `backend/app/database.py`
- **FastAPI** (6 connections)
- **test_health.py** (6 connections) — `backend/tests/test_health.py`
- **_rename_incompatible_legacy_table()** (5 connections) — `backend/app/migrations.py`
- **pages.py** (5 connections) — `backend/app/routers/pages.py`
- **get_session()** (4 connections) — `backend/app/database.py`
- **lifespan()** (4 connections) — `backend/app/main.py`
- **_columns()** (4 connections) — `backend/app/migrations.py`
- **Session** (4 connections)
- **_add()** (4 connections) — `backend/app/migrations.py`
- **health.py** (3 connections) — `backend/app/routers/health.py`
- **Request** (3 connections)
- **dashboard()** (2 connections) — `backend/app/routers/pages.py`
- **match_detail()** (2 connections) — `backend/app/routers/pages.py`
- **sources_page()** (2 connections) — `backend/app/routers/pages.py`
- **conftest.py** (2 connections) — `backend/tests/conftest.py`
- **Session** (1 connections)
- **favicon()** (1 connections) — `backend/app/main.py`
- **Preserve a pre-LoL table that reuses a current table name.      Earlier versions** (1 connections) — `backend/app/migrations.py`
- **Idempotent SQLite schema upgrades for installations predating Alembic.** (1 connections) — `backend/app/migrations.py`
- **health()** (1 connections) — `backend/app/routers/health.py`
- *... and 5 more nodes in this community*

## Relationships

- [Match Events & Odds Models](Match_Events_%26_Odds_Models.md) (7 shared connections)
- [Data Import Pipeline](Data_Import_Pipeline.md) (6 shared connections)
- [Core LoL Domain Models](Core_LoL_Domain_Models.md) (4 shared connections)
- [Config, HTTP & Utils](Config%2C_HTTP_%26_Utils.md) (2 shared connections)
- [Background Worker Jobs](Background_Worker_Jobs.md) (2 shared connections)

## Source Files

- `backend/app/database.py`
- `backend/app/main.py`
- `backend/app/migrations.py`
- `backend/app/routers/health.py`
- `backend/app/routers/pages.py`
- `backend/tests/conftest.py`
- `backend/tests/test_health.py`

## Audit Trail

- EXTRACTED: 111 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*