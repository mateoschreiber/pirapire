# Pirapire

Sistema analitico de cuotas deportivas construido con **FastAPI + SQLModel + SQLite**,
empaquetado en un unico contenedor Docker de bajo consumo.

> **Advertencia:** Pirapire es una herramienta **analitica**. Calcula probabilidades
> implicitas, cuotas justas, valor esperado (EV) y etiquetas de riesgo a partir de
> datos que el usuario ingresa. **No realiza scraping, no inicia sesion en casas de
> apuestas y no automatiza apuestas reales.**

## Caracteristicas

- API REST con FastAPI y documentacion automatica (Swagger UI).
- Persistencia ligera con SQLite (archivo unico en `data/pirapire.db`).
- Modelos con SQLModel: `Sport`, `Team`, `Match`, `OddsSnapshot`, `Prediction`.
- Motores de calculo puros para cuotas simples y combinadas.
- Un solo contenedor de aplicacion, sin PostgreSQL, Redis, Celery ni Node.

## Estructura

```
/opt/pirapire
├── backend/            # Codigo de la aplicacion (build context de Docker)
│   ├── app/
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── data/               # Base SQLite persistente (montada en /app/data)
├── logs/               # Logs (montada en /app/logs)
├── backups/            # Backups locales
├── .env                # Variables de entorno (no versionado)
└── .env.example
```

## Instalacion en /opt/pirapire

```bash
sudo mkdir -p /opt/pirapire
sudo chown "$(id -un):$(id -gn)" /opt/pirapire
git clone https://github.com/mateoschreiber/pirapire.git /opt/pirapire
cd /opt/pirapire
mkdir -p data logs backups
cp .env.example .env
```

Contenido de `.env`:

```
APP_NAME=Pirapire
APP_ENV=local
DATABASE_URL=sqlite:////app/data/pirapire.db
LOG_LEVEL=INFO
```

## Integracion con el docker-compose existente

Pirapire se agrega como el servicio `pirapire_app` dentro del `compose` ya presente
en el servidor (sin alterar los servicios existentes). Se crea un backup del compose
antes de modificarlo:

```bash
cp compose.yml compose.yml.bak_$(date +%Y%m%d_%H%M%S)
```

Servicio agregado:

```yaml
  pirapire_app:
    build: /opt/pirapire/backend
    container_name: pirapire_app
    env_file:
      - /opt/pirapire/.env
    ports:
      - "8090:8000"
    volumes:
      - /opt/pirapire/data:/app/data
      - /opt/pirapire/logs:/app/logs
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 20s
```

## Comandos de despliegue

Levantar **solo** el servicio de Pirapire (sin recrear los demas):

```bash
docker compose -f <COMPOSE_DETECTADO> up -d --build pirapire_app
docker compose -f <COMPOSE_DETECTADO> ps
```

## Acceso

- API / raiz: `http://SERVER_IP:8090/` (por defecto `http://192.168.1.54:8090/`)
- Swagger UI: `http://SERVER_IP:8090/docs`
- Healthcheck: `http://SERVER_IP:8090/health`

> Si el puerto 8090 estuviera ocupado se usa el siguiente disponible (8091, 8092, ...).

## Endpoints principales

| Metodo | Ruta            | Descripcion                                  |
| ------ | --------------- | -------------------------------------------- |
| GET    | `/`             | Info general de la app                       |
| GET    | `/health`       | Estado del servicio                          |
| POST   | `/sports`       | Crear deporte                                |
| GET    | `/sports`       | Listar deportes                              |
| POST   | `/teams`        | Crear equipo                                 |
| GET    | `/teams`        | Listar equipos                               |
| POST   | `/matches`      | Crear partido                                |
| GET    | `/matches`      | Listar partidos                              |
| POST   | `/odds/analyze` | Analizar una cuota simple (EV, riesgo)       |
| POST   | `/combo/analyze`| Analizar una combinada (parlay)              |

## Tests

Dentro del contenedor:

```bash
docker compose -f <COMPOSE_DETECTADO> exec pirapire_app pytest -q
```

En local (desde `backend/`):

```bash
pip install -r requirements.txt
ruff check .
pytest -q
```

## Datos de ejemplo (opcional)

```bash
docker compose -f <COMPOSE_DETECTADO> exec pirapire_app python -m app.seed
```
