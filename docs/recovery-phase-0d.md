# Recuperación — Fase 0D

Fecha: 2026-07-11 (America/Asuncion)

Estado: implementación validada en staging; despliegue y sincronizaciones controladas pendientes.

## Decisión de riesgo

El usuario autorizó expresamente el uso del override actual de Football-data.org aunque coincida con la credencial histórica. La credencial permanece cifrada con Fernet, fuera de `.env`, y solo puede activarse como `active_accepted_risk` mediante el endpoint administrativo protegido. La auditoría guarda fecha, actor y el código fijo `user_explicitly_accepted_known_credential`; nunca el valor.

## Arquitectura

### Football-data.org

- Fuente primaria de fixtures, resultados, selecciones y planteles.
- `SecretProvider` acepta estados `success` y `active_accepted_risk` con `source=ui`.
- Se eliminó el bloqueo temporal de bootstrap; no se reintroduce comparación con fingerprints históricos.
- Cliente v4 con pacing configurable, caché por job y un retry que respeta `Retry-After`.
- Nuevo `get_team_matches(team_id, status="FINISHED", limit=10)` sobre `/v4/teams/{id}/matches`.
- Consulta `/v4/competitions/WC/teams` e importación idempotente de selecciones y jugadores por IDs externos.
- Logs de requests y filas sin headers ni URLs con secretos.

### TheSportsDB

- Cliente separado y base fija `https://www.thesportsdb.com/api/v1/json`.
- Modo Free v1 con clave pública documentada como fallback `public_free`.
- Máximo 30 requests/minuto mediante espera mínima de 2 segundos, caché y `Retry-After`.
- Endpoints allowlisted: `searchteams`, `lookupteam`, `lookupplayer`, `lookup_all_players`, `lookupevent`, `lookupeventstats` y `lookuplineup`.
- Se valida status, content-type, JSON y estructura.
- Solo enriquece campos nulos de equipos existentes cuando deporte y nombre coinciden inequívocamente.
- Guarda procedencia en `FootballEntityMetadata`; no importa odds ni reemplaza resultados primarios.

### Riot

- Cliente con hosts y plataformas allowlisted; no admite URLs configurables.
- Implementa Platform Status, Account-V1, Summoner-V4 y Match-V5.
- Usa `X-Riot-Token` únicamente en memoria y nunca lo registra.
- Metadata no secreta: `key_type`, `default_platform`, `regional_routes` y `expires_at`.
- Development keys expiran automáticamente a las 24 horas; Personal es la opción recomendada.
- `RiotPlayerIdentity` exige identidad confirmada antes de resolver PUUID o consultar matches.
- `RiotMatchReference` queda separado de las tablas profesionales y marcado `personal_verified`.
- Leaguepedia continúa como fuente primaria de series y jugadores profesionales.
- Riot no configurado o expirado se omite sin convertir el sync global en fallo.

### Estado y prioridad

`IntegrationProviderState` persiste estado, error sanitizado, última comprobación, último éxito, requests, filas y cobertura por proveedor. Config muestra rol, modo, límite, cobertura y estado sin valores secretos.

Prioridad aplicada:

1. Aposta/Kambi para próximos eventos, mercados y odds.
2. Football-data.org para football estructurado.
3. TheSportsDB solo como metadata fallback.
4. Leaguepedia para esports profesional LoL.
5. Oracle's Elixir para backfill profesional.
6. Riot Match-V5 para identidades/matches personales confirmados.
7. Data Dragon para datos estáticos.

## Migraciones

- Columnas idempotentes en `IntegrationCredential`: aceptación de riesgo, metadata Riot y expiración.
- Tabla `IntegrationProviderState`.
- Tabla `FootballEntityMetadata`.
- Tablas `RiotPlayerIdentity` y `RiotMatchReference`.
- La clave maestra permanece en `/app/data/secrets/integration-master.key`, fuera de Git y SQLite.

## Validación previa al despliegue

- Backup: `backups/phase0d_20260711_124241/`.
- SQLite backup SHA-256: `c8388dfe96f7fd229687fd4caedea3a53bdbb1567d32b649c2c7117a80204763`.
- `.env` backup SHA-256: `58da4a8f57993f32879573cbc1ab0a8c5f11ee888cb47e5ab31afcecadeb4123`.
- `integrity_check=ok`.
- `pytest`: 173 passed, 5 skipped, 0 failed.
- `ruff` sobre todos los archivos tocados: correcto.
- `compileall`: correcto.
- Pruebas explícitas de rutas fijas, URL encoding, content-type, Retry-After, no retry de 401, expiración Riot, riesgo aceptado y ausencia de secretos en respuestas.

## Evidencia de despliegue

Se completará después del build y de las sincronizaciones controladas.
