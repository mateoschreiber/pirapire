# Despliegue de Pirapire

## Despliegue local / LAN

Pirapire está pensado para uso personal en LAN. Tras `docker compose up -d --build`
queda disponible en `http://IP-DEL-EQUIPO:${PIRAPIRE_PORT}/`.

## Variables relevantes

Definidas en `.env` (ver `.env.example`):

| Variable | Uso |
|----------|-----|
| `PIRAPIRE_PORT` | Puerto host publicado (mapea al 8000 interno). |
| `PIRAPIRE_CONTAINER_NAME` | Nombre del contenedor. |
| `APP_TIMEZONE` | Zona horaria para mostrar fechas. |
| `APP_PUBLIC_URL` | URL pública opcional (solo display; la app funciona sin ella). |
| `FOOTBALL_DATA_API_KEY` | API key opcional para datos de fútbol. |

## Cambiar el puerto

```bash
# en .env
PIRAPIRE_PORT=9095
```

```bash
docker compose up -d
```

## Cambiar APP_PUBLIC_URL

Es opcional y solo afecta enlaces/visualización. Si se deja vacío, la UI usa rutas
relativas y funciona igual:

```bash
# en .env
APP_PUBLIC_URL=http://mi-servidor.local:8090
```

## Backup de `data/`

El estado vive en `./data/pirapire.db`.

```bash
mkdir -p backups
cp data/pirapire.db "backups/pirapire_$(date +%Y%m%d_%H%M%S).db"
```

Restaurar: detener el contenedor, reemplazar `data/pirapire.db` por el backup, volver a levantar.

## Actualizar desde git

```bash
git pull
docker compose up -d --build pirapire_app
```

## Integración con otro stack / reverse proxy

El despliegue por defecto es **standalone** y no depende de ningún otro compose.
Para integrarlo a un stack existente o detrás de un reverse proxy, usa el ejemplo
opcional:

```bash
cp compose.override.example.yml compose.override.yml
# edita compose.override.yml (red externa, labels de proxy, volúmenes absolutos)
docker compose up -d
```

`compose.override.yml` es auto-mergeado por `docker compose`. Si no existe, no pasa nada.

### Notas para reverse proxy (no configurado por defecto)

- El contenedor expone la app en el puerto interno `8000`.
- Detrás de un proxy con TLS, no publiques el puerto directamente (comenta `ports`).
- Enruta el `Host` deseado hacia el servicio en el puerto `8000`.

## Healthcheck

El servicio define un healthcheck contra `http://localhost:8000/health`. Verifícalo con:

```bash
docker compose ps
curl -f http://localhost:${PIRAPIRE_PORT:-8090}/health
```
