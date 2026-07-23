# Config, HTTP & Utils

> 26 nodes

## Key Concepts

- **config.py** (10 connections) — `backend/app/config.py`
- **datetime_utils.py** (10 connections) — `backend/app/utils/datetime_utils.py`
- **http_client.py** (7 connections) — `backend/app/services/http_client.py`
- **test_timezone.py** (6 connections) — `backend/tests/test_timezone.py`
- **to_local()** (5 connections) — `backend/app/utils/datetime_utils.py`
- **get_client()** (4 connections) — `backend/app/services/http_client.py`
- **safe_get()** (4 connections) — `backend/app/services/http_client.py`
- **get_tz()** (4 connections) — `backend/app/utils/datetime_utils.py`
- **datetime** (4 connections)
- **format_local()** (4 connections) — `backend/app/utils/datetime_utils.py`
- **now_local()** (4 connections) — `backend/app/utils/datetime_utils.py`
- **offset_str()** (4 connections) — `backend/app/utils/datetime_utils.py`
- **request_json()** (3 connections) — `backend/app/services/http_client.py`
- **test_offset_and_format()** (3 connections) — `backend/tests/test_timezone.py`
- **Settings** (2 connections) — `backend/app/config.py`
- **safe_get_json()** (2 connections) — `backend/app/services/http_client.py`
- **ZoneInfo** (2 connections)
- **test_to_local_applies_minus_three_offset()** (2 connections) — `backend/tests/test_timezone.py`
- **BaseSettings** (1 connections)
- **Client** (1 connections)
- **Shared httpx wrapper for all external API calls.** (1 connections) — `backend/app/services/http_client.py`
- **Fetch JSON returning a structured result (never raises).      Returns {"ok": b** (1 connections) — `backend/app/services/http_client.py`
- **utils/__init__.py** (1 connections) — `backend/app/utils/__init__.py`
- **Timezone helpers: store UTC internally, display in APP_TIMEZONE.** (1 connections) — `backend/app/utils/datetime_utils.py`
- **Current UTC offset for APP_TIMEZONE, e.g. '-03:00'.** (1 connections) — `backend/app/utils/datetime_utils.py`
- *... and 1 more nodes in this community*

## Relationships

- [Database & Migrations](Database_%26_Migrations.md) (2 shared connections)
- [Core LoL Domain Models](Core_LoL_Domain_Models.md) (2 shared connections)
- [Match Events & Odds Models](Match_Events_%26_Odds_Models.md) (1 shared connections)
- [Data Import Pipeline](Data_Import_Pipeline.md) (1 shared connections)
- [Background Worker Jobs](Background_Worker_Jobs.md) (1 shared connections)
- [Oracle's Elixir Importer](Oracle%27s_Elixir_Importer.md) (1 shared connections)

## Source Files

- `backend/app/config.py`
- `backend/app/services/http_client.py`
- `backend/app/utils/__init__.py`
- `backend/app/utils/datetime_utils.py`
- `backend/tests/test_timezone.py`

## Audit Trail

- EXTRACTED: 88 (100%)
- INFERRED: 0 (0%)
- AMBIGUOUS: 0 (0%)

---

*Part of the graphify knowledge wiki. See [index](index.md) to navigate.*