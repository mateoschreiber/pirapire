# Pirapire

Pirapire es un **sistema analítico de apuestas deportivas** (fútbol y League of
Legends) que corre en un único contenedor Docker liviano. Importa cuotas,
sincroniza datos deportivos bajo demanda, estima probabilidades por mercado y
**recomienda automáticamente** las mejores apuestas individuales y combinadas.

> **Advertencia:** Pirapire es una herramienta **analítica**. No coloca apuestas,
> no inicia sesión en casas de apuestas y **no automatiza apuestas reales**.

## Características

- Dashboard con recomendaciones automáticas (mejores apuestas y combinadas).
- Modos de ranking: probabilidad, ganancia (EV), cuota y balanceado.
- Importación manual de cuotas por CSV (formato Aposta.LA) y de histórico LoL (Oracle's Elixir).
- Sincronización manual de datos: football-data.org (primaria) + OpenLigaDB (fallback), Riot Data Dragon (LoL).
- Catálogo de mercados con aliases ES/EN.
- Historial de predicciones/combinadas con marcado manual (won/lost/void/pending).
- API REST documentada (Swagger) y UI en HTML/CSS/JS vanilla.

## Arquitectura liviana

- **FastAPI + SQLModel + SQLite + Jinja2 + JavaScript vanilla.**
- Un solo contenedor de aplicación. Sin PostgreSQL, Redis, Celery, Node, React ni navegadores.
- Persistencia en un archivo SQLite dentro de `data/`.
- Toda actualización externa es **manual** (por botón o `POST`); no hay cron ni polling.

## Requisitos

- Docker Engine 20.10+ y Docker Compose v2.
- ~300 MB de disco para la imagen.
- (Opcional) Una API key gratuita de [football-data.org](https://www.football-data.org/) para datos de fútbol.

## Instalación rápida (cualquier PC)

```bash
git clone https://github.com/mateoschreiber/pirapire.git
cd pirapire
cp .env.example .env
# edita .env con tu editor preferido (nano, vim, etc.)
nano .env
docker compose up -d --build
docker compose ps
curl http://localhost:8090/health
```

Se puede instalar en **cualquier carpeta** (`~/pirapire`, `/srv/pirapire`, etc.).
Los datos y logs se guardan junto al proyecto en `./data` y `./logs`.

### Instalación opcional en /opt

```bash
sudo mkdir -p /opt/pirapire
sudo chown -R "$USER:$USER" /opt/pirapire
git clone https://github.com/mateoschreiber/pirapire.git /opt/pirapire
cd /opt/pirapire
cp .env.example .env && docker compose up -d --build
```

## Configuración de `.env`

Copia `.env.example` a `.env`. Variables clave:

| Variable | Descripción | Default |
|----------|-------------|---------|
| `PIRAPIRE_PORT` | Puerto host publicado | `8090` |
| `PIRAPIRE_CONTAINER_NAME` | Nombre del contenedor | `pirapire_app` |
| `APP_TIMEZONE` | Zona horaria de la UI | `America/Argentina/Buenos_Aires` |
| `APP_PUBLIC_URL` | URL pública (opcional, solo display) | vacío |
| `FOOTBALL_DATA_API_KEY` | API key de football-data.org (opcional) | vacío |
| `RECOMMENDER_DEFAULT_MODE` | Modo por defecto del recomendador | `probability` |

La API key **nunca** se versiona: vive solo en tu `.env` local.

## Primer arranque

```bash
docker compose up -d --build
docker compose logs -f pirapire_app   # opcional
curl http://localhost:8090/health     # {"status":"ok"}
```

## URLs locales

Reemplaza `localhost` por la IP del equipo si accedes desde otra máquina de la LAN.

- Dashboard: `http://localhost:8090/`
- Recomendaciones: `http://localhost:8090/recommendations/ui`
- Importaciones CSV: `http://localhost:8090/imports/ui`
- Mercados: `http://localhost:8090/markets/ui`
- Fuentes: `http://localhost:8090/sources/ui`
- Historial: `http://localhost:8090/history/ui`
- Swagger: `http://localhost:8090/docs`
- Healthcheck: `http://localhost:8090/health`

## Uso básico

### Importar odds de Aposta.LA por CSV

1. Abre **Importaciones** (`/imports/ui`).
2. Descarga la plantilla `aposta_odds_template.csv`.
3. Completa las cuotas que ves en la web pública y súbela con **Importar cuotas**.

### Actualizar fuentes de fútbol / LoL (manual)

En **Fuentes** (`/sources/ui`) usa los botones *Actualizar Fútbol* / *Actualizar LoL*.
Requiere conectividad a las APIs públicas; para fútbol conviene configurar `FOOTBALL_DATA_API_KEY`.

### Recalcular recomendaciones

En el **Dashboard** o en **Recomendaciones** elige el modo (probabilidad / ganancia /
odds / balanceado), ajusta los filtros y pulsa **Recalcular recomendaciones**.

### Historial y settle manual

Guarda una apuesta/combinada al historial desde las recomendaciones o el analizador,
y márcala como won/lost/void/pending en **Historial** (`/history/ui`).

## Backups

Los datos viven en `./data/pirapire.db`. Para respaldar:

```bash
mkdir -p backups
cp data/pirapire.db "backups/pirapire_$(date +%Y%m%d_%H%M%S).db"
```

## Actualización de la app

```bash
cd <ruta-de-pirapire>
git pull
docker compose up -d --build pirapire_app
```

Los datos en `./data` se conservan entre actualizaciones.

## Troubleshooting

- **El puerto 8090 está ocupado:** cambia `PIRAPIRE_PORT` en `.env` y vuelve a `docker compose up -d`.
- **`/health` no responde:** revisa `docker compose logs pirapire_app`.
- **Fútbol devuelve `partial`/429:** es el rate limit del plan gratuito; sube `FOOTBALL_DATA_REQUEST_DELAY_SECONDS` o baja `FOOTBALL_DATA_MAX_COMPETITIONS_PER_RUN`.
- **Sin recomendaciones:** primero importa cuotas (CSV) o sincroniza datos, luego *Recalcular*.

## Seguridad y secretos

Ver [SECURITY.md](SECURITY.md). En resumen: no commitees `.env`, no expongas API keys,
usa Pirapire solo en LAN/VPN y respalda tu SQLite.

## Documentación adicional

- [INSTALL.md](INSTALL.md) — instalación detallada.
- [DEPLOYMENT.md](DEPLOYMENT.md) — despliegue, puertos, reverse proxy, backups.
- [SECURITY.md](SECURITY.md) — seguridad y secretos.

## Fuentes oficiales

- Docker: <https://docs.docker.com/engine/install/>
- Docker Compose (env vars): <https://docs.docker.com/compose/how-tos/environment-variables/set-environment-variables/>
- FastAPI: <https://fastapi.tiangolo.com/>
- football-data.org: <https://www.football-data.org/documentation/quickstart>
- Riot Data Dragon: <https://developer.riotgames.com/docs/lol>

## Endpoints principales

`GET /health` · `GET /api/info` · `GET /docs` · `POST /recommendations/run` ·
`GET /recommendations/bets` · `GET /recommendations/combos` ·
`POST /imports/aposta-odds-csv` · `POST /sources/sync/{football,lol,all}` ·
`POST /odds/analyze` · `POST /combo/analyze` · `GET /history/predictions`
