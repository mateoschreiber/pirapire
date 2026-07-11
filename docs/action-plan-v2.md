# PIRAPIRE Action Plan V2

Este plan no fue ejecutado. Ordena las reparaciones por dependencia y mantiene como regla que cero recomendaciones es un resultado valido. Todas las migraciones requieren backup verificable, ensayo en copia y rollback documentado.

## Principios de ejecucion

- Bloquear promociones si falla identidad de evento, timezone, aislamiento o agrupacion no-vig.
- Conservar raw source IDs/labels y transformar a canonico sin destruir evidencia.
- Separar evento, mercado, outcome y snapshot; una odd es una version de outcome, no un evento.
- No entrenar ni recomendar hasta completar historicos, corte temporal y baseline.
- No bajar `min_sample`, edge, EV o validacion para fabricar recomendaciones.
- Trabajar primero con fixtures/copia de SQLite; acceso externo solo en fases marcadas.

## Fase 0. Contencion de seguridad (P0)

**Objetivo:** invalidar el secreto expuesto y cerrar transporte inseguro antes de seguir capturando.

**Archivos previstos:** `.env`/secret store operativo, `backend/app/services/import_wc_squads.py`, `backend/app/services/kambi_lol_connector.py`, Compose si se agrega secret mount.

**Tareas:**

1. Revocar la key literal en el proveedor; emitir una nueva con minimo privilegio.
2. Eliminar toda key de codigo y logs; decidir con el usuario si se reescribe Git remoto.
3. Inyectar secret por entorno y registrar solo `configured=true/false`.
4. Rehabilitar CA/hostname para Kambi; timeout, retry acotado y fallo cerrado.
5. Cambiar permisos `.env` a 0600/0640 y DB a 0640 con usuario/grupo de servicio.

**Pruebas:** secret scanner sobre Git completo; key antigua rechazada; key nueva funciona sin aparecer en logs; certificado invalido bloqueado; app/worker leen archivos y un usuario ajeno no.

**Aceptacion:** cero credenciales literales, TLS verificado y permisos restringidos.

**Datos externos:** si, rotacion y smoke GET del proveedor.  
**Rollback:** revertir solo wiring de secret manteniendo la key nueva fuera de Git; nunca restaurar la credencial revocada.  
**Decision requerida:** autorizacion para revocar y para reescribir historial Git.

## Fase 1. Build reproducible y baseline de auditoria

**Objetivo:** que app y worker ejecuten exactamente el mismo artefacto identificable antes de migrar datos.

**Archivos previstos:** `backend/Dockerfile`, `docker-compose.yml`, `backend/app/routers/health.py`, pipeline/deploy docs.

**Tareas:**

1. Construir una sola digest app/worker con labels OCI commit/build time.
2. Exponer commit/digest/schema version en `/api/info` una sola vez.
3. Agregar health del worker basado en heartbeat y DB compartida.
4. Capturar backup SQLite, SHA256, integrity/FK check y conteos de referencia.
5. Definir usuario no-root y umask del despliegue.

**Pruebas:** hashes app-worker iguales, `/api/info` coincide con release Git, tres healthchecks, restore del backup en staging.

**Aceptacion:** una release equivale a un commit, una digest y una schema version; rollback probado.

**Datos externos:** no.  
**Rollback:** redeploy de la digest anterior y restauracion del backup solo si hubo escritura de schema.

## Fase 2. Identidad estable, tiempo y snapshots (P0/P1)

**Objetivo:** modelar eventos estables y eliminar IDs de odds de URLs.

**Archivos previstos:** modelos/migracion nuevos, `models_imports.py`, `models_aposta.py`, parsers Aposta/Kambi, `aposta_sync.py`, `aposta_snapshot.py`, `event_matcher.py`, routers/pages.

**Tareas:**

1. Introducir `source_event_id`, `event_key`, `source_market_id`, `source_outcome_id`, raw labels y timezone-aware kickoff UTC.
2. Definir `event_key` por source+source_event_id; fallback documentado por sport+equipos+competition+kickoff normalizado.
3. Resolver `hoy/manana` con `ZoneInfo(APP_TIMEZONE)` y convertir una sola vez a UTC.
4. Crear entidades snapshot/event/market/outcome/price con unique constraints e historial append-only.
5. Upsert de `ApostaEvent`; expirar estado anterior sin duplicar evento.
6. Publicar `/events/{event_key}` y compatibilidad temporal de redirects para IDs viejos cuando sea inequivoco.
7. Incluir kickoff y source identity en matching; no usar busqueda amplia por texto solamente.

**Pruebas:** fixtures alrededor de 23:59/00:01 PY; dos eventos mismos equipos en fechas distintas; dos syncs identicos; sync con cambio de precio; union/interseccion de odds; URLs estables tras dos runs.

**Aceptacion:** mismo evento conserva URL, kickoff UTC/PY correcto, ninguna odd pertenece a dos eventos y la union por eventos coincide exactamente con active snapshot.

**Datos externos:** no para implementacion/fixtures; un GET minimo al final para validar IDs reales.  
**Rollback migracion:** backup previo; migracion expand-only; doble lectura bajo feature flag; revertir app a lector viejo sin borrar tablas nuevas; eliminar tablas solo en una release posterior.  
**Blocker:** confirmar IDs estables disponibles en Aposta/Kambi y retencion raw.

## Fase 3. Mercados canonicos y no-vig (P0)

**Objetivo:** conservar todas las dimensiones y calcular porcentajes solo sobre mercados completos compatibles.

**Archivos previstos:** market catalog/aliases, Kambi parser, models markets/imports, odds engine, event API/template.

**Tareas:**

1. Parsear criterion/betOffer/outcome IDs y raw labels sin contains mapping generico.
2. Separar `period`, `map_number`, `line`, `team`, `player`, `role`, prop y side.
3. Versionar mappings; unmapped permanece visible pero no recibe codigo generico.
4. Definir expected outcomes por market type y validar completitud.
5. Calcular implied por outcome; no-vig solo dentro de `source_market_id` completo.
6. Mostrar “no disponible” para grupos incompletos, incompatibles o suspendidos.
7. Unificar `market_count` como mercados distintos; exponer `odds_count` aparte.

**Pruebas:** golden payloads football/LoL; props de dos jugadores/lineas/mapas; Odd/Even; handicap; suspended outcomes; suma no-vig y formula manual.

**Aceptacion:** cero grupos de 4-64 outcomes por colision; no-vig suma 1 solo donde corresponde; labels y conteos coinciden API/DB/UI.

**Datos externos:** no con snapshots raw conservados; GET minimo de verificacion final.  
**Rollback:** feature flag al parser anterior solo para captura raw, nunca para publicar no-vig; conservar columnas nuevas.

## Fase 4. Fuentes e historicos reales (P1)

**Objetivo:** completar 10 partidos/series y aliases antes de estadisticas.

**Archivos previstos:** football client/sync, Leaguepedia sync, Oracle importer, alias services, source run models/routes, worker.

**Tareas:**

1. Football: implementar `/teams/{id}/matches?status=FINISHED&limit=10`, cache por team y cutoff antes del kickoff.
2. Persistir alias Aposta-source con confidence y revision manual para ambiguos.
3. Leaguepedia: corregir nombre de funcion, offset real y paginacion de Games/Players; incorporar Teams/rosters.
4. Elegir/importar Oracle's Elixir real para backfill; no asumir descarga disponible.
5. Normalizar serie y mapa (`series_id`, `game_number`, best-of); conservar mapas completos.
6. Matriz operacional por fuente con prioridad, ultima ok, ultimo error y coverage.
7. Cache/rate limit: honor Retry-After, backoff, max pages y budget por run.

**Pruebas:** paginas 0/1/ultima; dedupe al reimportar; aliases actuales; 10 FINISHED previos; 10 series con mapas; fila 11 sigue en DB.

**Aceptacion:** 10/10 o estado n/10 justificado por fuente para cada participante; sin mezclar mapas con series; source runs completos.

**Datos externos:** si, es la fase principal dependiente de proveedores.  
**Rollback:** imports append-only por batch; desactivar batch y reconstruir vistas canonicas; nunca borrar raw snapshots.  
**Blocker:** seleccionar fuente LoL primaria/licencia y confirmar cobertura Tier One football.

## Fase 5. Jugadores y relaciones temporales (P1)

**Objetivo:** cubrir planteles/rosters y estadisticas reales de participantes actuales.

**Archivos previstos:** modelos player/team membership, football squad importer, Leaguepedia/Oracle importers, worker y APIs/UI.

**Tareas:**

1. Eliminar key literal y usar cliente football compartido con telemetry/retry.
2. Ejecutar roster al start solo si stale, luego schedule 24 h.
3. Modelar membership con `valid_from/valid_to`, source y confidence.
4. Importar football posicion/dorsal; LoL role/champion/KDA/CS/gold/damage.
5. Resolver jugadores de markets Aposta a player IDs; mantener unresolved explicito.
6. Publicar coverage por evento/equipo.

**Pruebas:** cambio de roster, jugador homonimo, equipo sin squad, null vs cero, promedios manuales por jugador.

**Aceptacion:** cobertura de todos los equipos actuales; ninguna fila artificial; null no se presenta como 0.

**Datos externos:** si.  
**Rollback:** desactivar batch/membership nuevo por source y volver a vista previa; raw intacto.

## Fase 6. Servicio unico de ventanas y estadisticas (P1)

**Objetivo:** separar descriptivos reales de forecasts y usar exactamente las unidades requeridas.

**Archivos previstos:** nuevo history/window service, football/LoL metrics, event statistics router/schema, templates.

**Tareas:**

1. API comun con sport, entity, unit, window=10, cutoff, source y sample size.
2. Football: FINISHED y `start_time < event kickoff`; ordenar fecha real.
3. LoL: ultimas 10 series; agregar mapas por serie antes de promediar.
4. Responder `n/10`, periodo, source y campos null; no ocultar equipo sin datos.
5. Recalcular frecuencias/promedios con denominadores auditables.
6. Eliminar alias hardcodeado de la ruta y usar entity map persistido.

**Pruebas:** calculos manuales de los cuatro equipos football y un matchup LoL; cutoff; 11a fila; orden distinto a created_at; null/zero.

**Aceptacion:** UI/API/SQL coinciden y cada estadistica expone muestra/unidad/periodo/fuente.

**Datos externos:** no una vez completada fase 4/5.  
**Rollback:** mantener endpoint versionado anterior hasta comparar; switch de frontend por feature flag.

## Fase 7. API y UX funcional (P1/P2)

**Objetivo:** contratos coherentes, estados completos y navegacion responsive/accesible.

**Archivos previstos:** routers main/health/data/events/pages, templates, `app.js`, CSS, OpenAPI schemas.

**Tareas:**

1. Eliminar `/api/info` duplicada; contratos tipados HTML/JSON/download.
2. Definir 404 real para recurso ausente, 409 para sync lock/conflicto y 422 validado.
3. Reparar Equipos y contrato upcoming LoL.
4. Header detalle desde el mismo DTO de API; separar odds/markets.
5. Estados loading/success/empty/error por bloque; mostrar ambos equipos y `n/10`.
6. Reemplazar `div onclick` por links/buttons focusables; labels y foco visibles.
7. Reemplazar HTML concatenado por DOM/textContent o escape; agregar CSP.
8. Encapsular tablas con scroll y eliminar overflow de pagina a 375.

**Pruebas:** contract tests 200/404/409/422; Playwright a 375/768/1366/1920; consola/network; teclado; payload XSS; clock PY.

**Aceptacion:** cero 4xx inesperados/spinners/overflow; todos los eventos clickables por teclado; conteos UI=API=SQLite.

**Datos externos:** no, usar fixtures deterministas.  
**Rollback:** assets versionados y feature flag a UI anterior; API v1 permanece durante una release.

## Fase 8. Forecasts, backtests y recomendaciones validadas

**Objetivo:** habilitar recomendaciones solo donde un modelo temporalmente valido supera baseline.

**Archivos previstos:** features football/LoL, backtesting, model registry nuevo, recommendation service/models, combo builder, UI.

**Tareas:**

1. Congelar datasets/versiones y cortes walk-forward por evento.
2. Baselines por mercado; Brier, log-loss, calibracion, sample y CI.
3. Registrar model version, train cutoff, features, coverage y validation status.
4. Clasificar descriptivo, heuristic/experimental y validated forecast en API/UI.
5. Gate estricto: mercado/source/model no validado no recomienda.
6. Combos solo de legs validadas; reemplazar constante de correlacion por politica/modelo validado o deshabilitar.
7. Invalidar/etiquetar las 7 recomendaciones legacy no reproducibles.

**Pruebas:** leakage temporal, baseline regression, calibracion, mercado unsupported, cero recommendations, combos sin misma event/correlacion no validada.

**Aceptacion:** cada recomendacion enlaza modelo/backtest que supera baseline; si ninguno lo hace, resultado estable es cero.

**Datos externos:** no si fases 4-6 ya poblaron datasets; si para ampliar cobertura.  
**Rollback:** desactivar modelo/version en registry y volver a cero recomendaciones; no bajar gates.

## Fase 9. Workers, CI y despliegue gradual

**Objetivo:** operar todas las fases con telemetry, pruebas de regresion y rollback comprobado.

**Archivos previstos:** worker, job run models, Compose/health, CI, tests Playwright y runbooks.

**Tareas:**

1. Persistir ultimas ejecuciones por job con start/end/duracion/filas/error/retry.
2. Lock distribuido/DB, `max_instances=1`, coalesce y backoff observable.
3. Trigger post-partido basado en estado/cambio, sin full sync innecesario.
4. Gates CI: compileall, ruff, pytest, node check, Playwright y migracion up/down en copia.
5. Canary read-only: comparar parser viejo/nuevo sobre raw sin publicar.
6. Backup, deploy app+worker atomico, smoke, monitor y promocion.

**Pruebas:** doble worker, crash mid-job, 429, fuente caida, DB locked, rollback digest/schema, post-finish update.

**Aceptacion:** cinco runs por job visibles, ningun duplicado, health degrada correctamente y rollback ensayado.

**Datos externos:** parcialmente para fault/smoke; la mayoria con mocks.  
**Rollback despliegue:** detener writers, desplegar digest anterior compatible, revertir feature flags; restaurar backup solo ante corrupcion/transformacion irreversible y despues de conservar copia forense.

## Secuencia y dependencias

| Orden | Fase | Depende de | Puede hacerse sin datos externos |
|---:|---|---|---|
| 0 | Contencion seguridad | decision credencial | No completamente |
| 1 | Build/baseline | ninguna | Si |
| 2 | Identidad/tiempo/snapshot | 1 | Si, salvo smoke final |
| 3 | Mercados/no-vig | 2 | Si con raw fixtures |
| 4 | Fuentes/historicos | 0-3 | No |
| 5 | Jugadores | 0, 4 | No |
| 6 | Ventanas/estadisticas | 2, 4, 5 | Si |
| 7 | API/UX | 2, 3, 6 | Si |
| 8 | Modelos/recomendaciones | 3, 4, 6 | Si con dataset completo |
| 9 | Workers/CI/deploy | todas | Parcialmente |

## Riesgos y rollback transversal

- **Riesgo de migracion:** 7.629 odds y capas paralelas. Mitigar con expand-only, backup SHA256, shadow read y unique constraints inicialmente no destructivas.
- **Riesgo de IDs:** redirects ambiguos. Solo redirigir cuando una fila vieja resuelve exactamente un `event_key`; si no, 409/410 explicito.
- **Riesgo timezone:** naive/aware mezclados. Migrar con columna nueva UTC y conservar raw original; no sobreescribir hasta reconciliar.
- **Riesgo source/licencia:** Oracle/Leaguepedia pueden no cubrir o cambiar. Mantener prioridad/config y estado unavailable, no inventar datos.
- **Riesgo de modelo:** muestras pequenas. Mantener recomendaciones apagadas por mercado hasta superar baseline.
- **Riesgo operativo:** app y worker escriben a SQLite. Coordinar ventana, detener writers para migracion, integrity/FK check antes/despues y canary.

## Criterio de cierre del programa

1. Cero P0/P1 abiertos.
2. URLs estables y kickoffs correctos tras al menos dos syncs que crucen medianoche PY.
3. Aislamiento y union exacta de odds por evento/source IDs.
4. No-vig solo en mercados completos compatibles.
5. Coverage real n/10 y jugadores para todos los participantes actuales.
6. UI/API/SQLite coherentes en cuatro viewports, teclado y consola limpia.
7. App/worker misma release, jobs observables, CI completa verde.
8. Recomendaciones solo con modelos que superan baseline; cero sigue siendo aceptable.
