# Pirapire

Sistema analitico de cuotas deportivas construido con **FastAPI + SQLModel + SQLite**
y una interfaz web liviana con **Jinja2 + HTML/CSS/JS vanilla**, empaquetado en un
unico contenedor Docker de bajo consumo.

> **Advertencia:** Pirapire es una herramienta **analitica**. Calcula probabilidades
> implicitas, cuotas justas, valor esperado (EV) y etiquetas de riesgo a partir de
> datos que el usuario ingresa. **No realiza scraping, no consume APIs externas, no
> inicia sesion en casas de apuestas y no automatiza apuestas reales.**

## Caracteristicas

- API REST con FastAPI y documentacion automatica (Swagger UI en `/docs`).
- Interfaz web (dashboard) servida por el mismo servicio, sin React/Node/Vite/CDN.
- Persistencia ligera con SQLite (archivo unico en `data/pirapire.db`).
- Modelos con SQLModel: `Sport`, `Team`, `Match`, `OddsSnapshot`, `Prediction`.
- Motores de calculo puros para cuotas simples y combinadas.
- Un solo contenedor de aplicacion, sin PostgreSQL, Redis, Celery ni Node.

## Interfaz web

La raiz `/` ahora renderiza un **dashboard HTML** (ya no JSON). El JSON informativo
anterior sigue disponible en `GET /api/info`.

| Pagina                 | Ruta            | Descripcion                                  |
| ---------------------- | --------------- | -------------------------------------------- |
| Dashboard              | `/`             | Tarjetas resumen y accesos rapidos           |
| Deportes               | `/sports/ui`    | Alta y listado de deportes                   |
| Equipos                | `/teams/ui`     | Alta y listado de equipos                    |
| Partidos               | `/matches/ui`   | Alta y listado de partidos                   |
| Analizador de Cuotas   | `/odds/ui`      | Analiza una cuota individual (EV, riesgo)    |
| Simulador de Combinadas| `/combo/ui`     | Analiza combinadas (parlay) con patas        |
| Historial              | `/history/ui`   | Placeholder para futuro historial            |
| Configuracion          | `/settings/ui`  | Configuracion local (solo lectura)           |

Recursos estaticos: `app/static/css/styles.css` y `app/static/js/app.js`, servidos
bajo `/static`. La UI consume los endpoints API existentes via `fetch`.

## Estructura

```
/opt/pirapire
├── backend/
│   ├── app/
│   │   ├── routers/        # health, sports, teams, matches, odds, combo, pages
│   │   ├── services/       # odds_engine, combo_engine
│   │   ├── templates/      # base + una plantilla por pagina (Jinja2)
│   │   ├── static/         # css/ y js/ (sin CDN)
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   └── schemas.py
│   ├── tests/
│   ├── Dockerfile
│   ├── pytest.ini
│   └── requirements.txt
├── data/    logs/    backups/
├── .env     .env.example
```

## Endpoints API

| Metodo | Ruta            | Descripcion                                  |
| ------ | --------------- | -------------------------------------------- |
| GET    | `/api/info`     | Info general (JSON)                          |
| GET    | `/health`       | Estado del servicio                          |
| POST   | `/sports`       | Crear deporte                                |
| GET    | `/sports`       | Listar deportes                              |
| POST   | `/teams`        | Crear equipo                                 |
| GET    | `/teams`        | Listar equipos                               |
| POST   | `/matches`      | Crear partido                                |
| GET    | `/matches`      | Listar partidos                              |
| POST   | `/odds/analyze` | Analizar una cuota simple                    |
| POST   | `/combo/analyze`| Analizar una combinada                       |

## Fase 2 — Conectores y sincronizacion manual

**Conectores implementados:**

| Fuente | Deporte | Rol | Auth |
|--------|---------|-----|------|
| football-data.org | Futbol | Primaria: fixtures, resultados, standings, equipos | `X-Auth-Token` desde `.env` |
| OpenLigaDB | Futbol | Fallback: solo si la primaria no funciona o `OPENLIGADB_*` esta configurado | Sin auth |
| Riot Data Dragon | LoL | Unica: parches y campeones (datos estaticos) | Sin auth |

**Sincronizacion:** exclusivamente manual mediante botones en `GET /sources/ui`
(`Actualizar Futbol` / `Actualizar LoL` / `Actualizar Todo`). No hay cron, scheduler ni polling.

**Endpoints de sync:** `POST /sources/sync/football`, `POST /sources/sync/lol`,
`POST /sources/sync/all`, `POST /sources/sync/{source_slug}`

**Historial:** `GET /source-runs` y `GET /source-runs/ui`

**Datos cargados:** `GET /data/football/*`, `GET /data/lol/*` y sus UIs.

**Raw snapshots:** cada respuesta externa se guarda con `payload_hash`; se deduplican.

## Fase 3 — Importadores CSV, catálogo de mercados e historial

- **Market Catalog** (`/markets/ui`, `GET /markets`, `POST /markets/seed`): mercados de
  fútbol y LoL con `source_status` (supported/manual_only/partial), `risk_level` y aliases
  ES→código para mapear textos de Aposta.LA.
- **Importadores CSV manuales** (`/imports/ui`): Aposta.LA (cuotas/mercados) y Oracle's
  Elixir (histórico LoL). Solo se importa al subir archivo o `POST` manual — sin scraping.
  Cada carga crea un `ManualImportBatch` y registra `ManualImportError` por fila sin abortar
  todo el archivo. Mercados no reconocidos quedan como `unmapped` con warning.
  Plantillas descargables: `GET /imports/templates/aposta-odds` y `/imports/templates/oracles-elixir`.
- **Historial real** (`/history/ui`): el Analizador de Cuotas (`save=true`) persiste
  `PredictionHistory` y el Simulador (`save=true`) persiste `ComboHistory`/`ComboLegHistory`.
  Marcado manual won/lost/void/pending vía `POST /history/{predictions,combos}/{id}/settle`.

## Fuentes de datos (registro)

Capa de fuentes externas rankeadas por confiabilidad. En esta fase es **solo
lectura**: registro de fuentes, ranking y resolucion de fuente primaria por
`sport` + `data_type`. **No hay conectores de red ni sincronizacion automatica**;
la actualizacion manual y los conectores llegan en fases siguientes.

- `GET /sources` — fuentes registradas con estado (`enabled` / `disabled_missing_env` / `disabled_reference_only`).
- `GET /sources/rankings` — ranking por deporte (`football`, `lol`).
- `GET /sources/capabilities` — capacidades por `data_type` y fuente primaria.
- `POST /sources/seed` — persiste el registro en las tablas `DataSource` / `SourceCapability`.
- UI: `GET /sources/ui` (menu **Fuentes**).

## Integracion con el docker-compose existente

Pirapire corre como el servicio `pirapire_app` dentro del `compose` presente en el
servidor (`/opt/licitaciones/compose.yml`), sin alterar los servicios existentes.
Se crea un backup del compose antes de cualquier modificacion.

## Comandos de despliegue

```bash
cd /opt/pirapire
docker compose -f /opt/licitaciones/compose.yml config
docker compose -f /opt/licitaciones/compose.yml up -d --build pirapire_app
docker compose -f /opt/licitaciones/compose.yml ps pirapire_app
```

## Acceso

- Dashboard: `http://192.168.1.54:8090/`
- Swagger UI: `http://192.168.1.54:8090/docs`
- Healthcheck: `http://192.168.1.54:8090/health`
- Info JSON: `http://192.168.1.54:8090/api/info`

## Tests

```bash
docker compose -f /opt/licitaciones/compose.yml exec pirapire_app pytest -q
docker compose -f /opt/licitaciones/compose.yml exec pirapire_app ruff check .
```

En local (desde `backend/`):

```bash
pip install -r requirements.txt
ruff check .
pytest -q
```

## Datos de ejemplo (opcional)

```bash
docker compose -f /opt/licitaciones/compose.yml exec pirapire_app python -m app.seed
```
