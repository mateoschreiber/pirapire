# Recuperación — Fase 0D

Fecha: 2026-07-11 (America/Asuncion)

Estado: implementado, desplegado y validado; football activo con riesgo aceptado, TheSportsDB operativo y Riot preparado pero no configurado.

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

### Build y migración

- Commit técnico: `338b7804ccbe56cfd851aa68fe13258bb08011f5`.
- Imagen única app/worker: `sha256:d3094a402be2042d38e8088fa013032639e1309951296315c3b64413265068d6`.
- `BUILD_COMMIT` observado dentro del contenedor: coincide con el commit técnico.
- Migraciones: columnas y cuatro tablas nuevas presentes.
- SQLite posterior: `integrity_check=ok`.
- Volúmenes preservados.

### Estado por proveedor

| Proveedor | Estado | Fuente | Cobertura | Último job |
|---|---|---|---|---|
| Football-data.org | `active_accepted_risk` | `ui` | 84 equipos, 1.249 jugadores, 105 partidos | success; 8 requests observados |
| TheSportsDB | success, Free v1 | `ui` | 3 registros de metadata fallback | success; 5 requests observados |
| Leaguepedia | success, primaria esports | sin clave | 504 juegos pro, 3.610 filas de jugadores | success; 2 requests lógicos |
| Riot API | unconfigured | unconfigured | 0 identidades confirmadas, 0 matches personales | omitido sin fallo global |
| Data Dragon | success | sin clave | 173 campeones | success; 2 requests |

La credencial Football-data.org fue probada desde el override cifrado y activada por el endpoint administrativo como `active_accepted_risk`. `accepted_risk_at`, `accepted_by` y el motivo fijo quedaron registrados sin valor secreto. El archivo `.env` y el bind mount activo no contienen la variable ni la credencial.

### Sincronizaciones controladas

- Football run 12: `success`, 1.249 insertados, 0 actualizados, 7 omitidos, 0 errores.
- Football run 15: `success`, 0 insertados, 1.249 actualizados, 7 omitidos, 0 errores.
- Idempotencia football: antes y después permanecieron 84 equipos, 1.249 jugadores con 1.249 claves únicas, y 105 partidos con 105 IDs únicos.
- `get_team_matches(..., FINISHED, 10)`: HTTP 200, 3 resultados y límite respetado.
- TheSportsDB run 13: `success`, 2 metadatos insertados, 2 equipos enriquecidos, 3 omitidos.
- TheSportsDB run 16: `success`, 1 metadato insertado, 1 equipo enriquecido, 4 omitidos; 3 metadatos totales y 3 claves de procedencia únicas.
- Leaguepedia run 14: `success`, 3.610 insertados, 1.083 actualizados, 0 errores.
- Data Dragon run 17: `success`, 173 actualizados, 0 errores.
- Riot no se ejecutó: no hay key ni PUUID confirmado. Esta omisión no afectó las demás fuentes.

No se observaron 429 durante los syncs reales. Football aplicó espera de 7 segundos y TheSportsDB espera mínima de 2 segundos. Los tests simulan 429 y verifican `Retry-After`; 401/403 no se reintentan.

### Seguridad

- Escaneo de la credencial efectiva: ausente en SQLite en claro, `.env`, logs de archivo, HTML de Config, respuesta de integraciones y `/api/info`.
- Logs de contenedores: cero coincidencias de `Authorization`, `X-Auth-Token`, `X-Riot-Token` o asignaciones de la variable.
- `docker inspect`: cero asignaciones residuales de football-data.org.
- GET administrativo no devuelve `encrypted_value` ni valores descifrados.
- TheSportsDB no usa v2 ni se registra como fuente de odds.
- Riot mantiene las partidas `personal_verified` separadas de Leaguepedia.

### UI y checks finales

- Config: 7 cards fijas; Football muestra “Activa — riesgo aceptado”.
- TheSportsDB muestra Free API v1 y 30 requests/minuto.
- Riot muestra tipo, plataforma, ruta, expiración y estado no configurado.
- Tres inputs secretos vacíos; ningún valor precargado.
- Light/dark sin overflow a 375, 768, 1366 y 1920 px; cero `pageerror`.
- Capturas en `docs/phase0d-captures/`.
- `pytest`: 173 passed, 5 skipped, 0 failed.
- `ruff` sobre archivos tocados: correcto.
- `compileall`: correcto.
- `node --check`: correcto.
- `git diff --check`: correcto.
- App: healthy.
- Worker: healthy, misma imagen que app.
- Browser: healthy.

## Re-verificación y corrección (2026-07-11, ronda 2)

Al re-ejecutar la suite completa se detectó un fallo dependiente del orden en
`tests/test_pages.py::test_dashboard_event_cards_are_keyboard_accessible_links`.
Cuando pruebas previas siembran eventos de Aposta, el dashboard renderiza
`event-card`s y activa la aserción `"onclick=" not in html`, que capturaba el
`onclick` inline del botón de tema en `base.html`. El handler ya se enlazaba por
JavaScript (`addEventListener` en `initTheme`), de modo que el `onclick` inline
era redundante. Se eliminó y se agregó `type="button"`.

- Commit de corrección: `12c2ea085dbb9e425a20fc2da2f0a2eb1ab044c1`.
- Imagen única app/worker reconstruida: `sha256:bdc9524566faa6396a2dce24fb8e8d1c71ec811f16df2d05199b8147484c7145`.
- `BUILD_COMMIT` dentro del contenedor: `12c2ea08...` (coincide).
- App y worker recreados preservando volúmenes; los tres contenedores `healthy`.

### Backup previo

- Backup: `backups/phase0d_fix_20260711_161704/`.
- SQLite backup SHA-256: `0888d5cd393d6a4c0dbfabb08bece11b5888f8839ed2268c4ab65e12956a6c06`.
- `.env` backup SHA-256: `58da4a8f57993f32879573cbc1ab0a8c5f11ee888cb47e5ab31afcecadeb4123`.
- `integrity_check=ok`.

### Verificaciones

- `pytest` completo: 173 passed, 5 skipped, 0 failed.
- `pytest` phase 0D (`test_phase0d_clients`, `test_football_data_org`, `test_integration_settings`): 31 passed.
- `ruff` sobre los archivos de la fase 0D: `All checks passed!`.
- `compileall`: correcto.
- `node --check` sobre `app.js`: correcto.
- `git diff --check`: correcto.
- HTML desplegado: 0 `onclick=Pirapire.toggleTheme`, botón `themeToggle` presente.

### Sincronización controlada post-deploy

Ejecutada dos veces por proveedor para confirmar idempotencia (conteos antes = después):

- Estado inicial y final idéntico: 84 equipos, 1.249 jugadores (1.249 claves únicas), 105 partidos (105 IDs únicos), 3 metadatos TheSportsDB.
- Football run 1: `success`, 0 insertados, 1.401 actualizados, 11 omitidos, 0 errores.
- Football run 2: `success`, 0 insertados, 1.249 actualizados, 12 omitidos, 0 errores.
- TheSportsDB run 1 y 2: `success`, 0 insertados, 0 actualizados, 5 omitidos (metadata ya presente; sin odds).
- Riot run 1: `success`, 1 omitido — `unconfigured`, omitido sin convertirse en fallo global.
- Sin 429 observados; football respetó pacing de 7 s y TheSportsDB espera mínima de 2 s.

### Matriz de estado por proveedor (post-deploy)

| Proveedor | Estado | Requests | Filas | Cobertura |
|---|---|---|---|---|
| Football-data.org | `success` (`active_accepted_risk`, `source=ui`) | 8 | 1.256 | 7 competiciones |
| TheSportsDB | `success` (Free v1) | 5 | 5 | metadata fallback |
| Leaguepedia | `success` | 2 | 4.693 | 361 filas scoreboard |
| Riot API | `unconfigured` | 0 | 0 | 0 identidades/matches |
| Data Dragon | `success` | 2 | 174 | 173 campeones |

### Seguridad (re-escaneo)

- `1b7f` (last4 football) ausente de `.env`.
- Logs del contenedor app: 0 coincidencias de `X-Auth-Token`/`X-Riot-Token`/`Authorization:`.
- HTML de inicio: 0 coincidencias de tokens o `api_key`.
- `docker inspect`: 0 asignaciones residuales de football-data.org ni cabeceras de token.
