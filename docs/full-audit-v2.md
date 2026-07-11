# PIRAPIRE Full Audit V2

**Fecha de corte:** 2026-07-11 00:12:36 America/Asuncion (03:12:36 UTC)  
**Modo:** solo lectura. No se editaron codigo, `.env`, SQLite, Dockerfile ni Compose; no se ejecutaron migraciones ni sincronizaciones. Las unicas escrituras son este informe, el plan y siete capturas.  
**Objetivo auditado:** captura automatica de Aposta.LA, proximos partidos de Mundial y LoL, historial real, ventanas de 10, jugadores, probabilidades correctas, modelos validados, workers y UX responsive.

## Resumen ejecutivo

El sistema captura automaticamente tres matchups actuales y el aislamiento del hotfix funciona en el corte: cada detalle devolvio solo sus 5, 5 y 865 odds; la union fue exactamente las 875 odds activas y no se reprodujo la hipotesis de un detalle con todas las odds globales. Esto evita clasificar ese caso concreto como P0.

El producto no es confiable todavia para interpretar horarios o probabilidades LoL. Se confirmaron tres P0: (1) los kickoffs de futbol derivados de `hoy/manana` estuvieron un dia adelantados durante cuatro batches por usar UTC como fecha de referencia; (2) el detalle aplica no-vig a outcomes incompatibles, con grupos de hasta 64 selecciones y overrounds superiores a 3.300%; y (3) existe una credencial real hardcodeada, versionada y desplegada. LoL conserva 865 filas del mismo matchup, pero pierde ID de evento/mercado/outcome, jugador, linea real y numero de mapa; el campo `line` contiene frecuentemente el numero de mapa.

Los enlaces publicos no identifican eventos: usan el ID de una fila `ImportedOdds`. En la propia auditoria los IDs 5023/5028/5033 pasaron de 200 a 404 al siguiente sync, y luego fueron sustituidos por 5880/5885/5890 y 6755/6760/6765. No existen columnas persistidas `event_key` o `source_event_id`. Cada sync agrega nuevos `ApostaEvent`, todos quedan `active`: 43 filas representan solo 9 identidades observadas.

Historicos y jugadores estan incompletos. Cada seleccion vigente tiene 5/10 partidos FINISHED. Hanwha tiene 10 mapas, equivalentes aproximadamente a 3 series, y Lyon 0; no hay estadisticas de kills/torres. Hay 0 jugadores de futbol, 0 jugadores LoL y 0 aliases de equipo LoL. La importacion de jugadores de Leaguepedia falla por `NameError` y su paginacion no aplica `offset`.

La automatizacion basica opera: Aposta cada 12 minutos, deportes cada 4 horas y planteles cada 24 horas, con `coalesce=True` y `max_instances=1`. App y worker comparten la misma SQLite y configuracion, pero usan identidades de imagen distintas; el worker no tiene healthcheck ni version de build, y el job de planteles contiene la credencial hardcodeada.

`pytest` pasa (137 passed, 5 skipped), pero no hay tests de detalle de eventos, aislamiento, no-vig ni Playwright; 57 asserts solo verifican status 200. `ruff` falla con 74 errores, incluidos el `NameError` productivo. Playwright confirma reloj correcto y dashboard sin overflow en cuatro anchos, pero las vistas de datos desbordan en movil, Equipos queda en `Cargando...` con un 404, y las tarjetas de evento no son accesibles por teclado.

## Estado contra objetivos del producto

| Objetivo | Estado | Evidencia |
|---|---|---|
| Captura automatica de eventos y odds Aposta.LA | Parcial | Worker cada 12 min; 875 odds activas. IDs de origen se descartan y el conteo oscilo 830/832/857/875. |
| Futbol: solo proximos Mundial | Parcial | Dos matchups de Copa del Mundo vigentes. El parser desplazo su fecha un dia hasta medianoche local. |
| LoL: solo proximos disponibles | Parcial | Un matchup MSI; 865 odds del mismo evento, pero sin identidad estable ni dimensiones correctas. |
| Conservar historial adicional | Parcial | 7.629 odds historicas, 105 partidos de futbol, 490 mapas LoL; no hay snapshot ID util ni series normalizadas. |
| Ultimos 10 por seleccion/series LoL | No cumple | Futbol 5/10; Hanwha 3/10 series aproximadas, Lyon 0/10; LoL usa mapas y ventana 20/30. |
| Jugadores y estadisticas reales | No cumple | 0 jugadores en ambos deportes; kills/torres LoL nulos; Leaguepedia players falla. |
| Implied y no-vig correctos | No cumple | `1/odds` es correcto; no-vig se aplica a grupos incompatibles y se presenta como valido. |
| Separar descriptivo, forecast y recomendacion | Parcial | Campos separados en recomendaciones, pero UI mezcla etiquetas y no hay validacion suficiente; cero recomendaciones actuales es correcto. |
| Actualizacion automatica por workers | Parcial | Scheduler activo; falta health/telemetria completa, roster inicial y actualizacion post-partido dedicada. |
| UI responsive, simple y navegable | Parcial | Dashboard correcto en 4 anchos; otras vistas desbordan, Equipos rompe LoL y eventos no son accesibles por teclado. |

## Metricas verificadas

| Metrica | Valor al corte |
|---|---:|
| Odds activas / historicas | 875 / 7.629 |
| Odds activas matched | 10 (1,14%) |
| Odds activas con `market_id` / sin `market_id` | 470 / 405 |
| Matchups actuales | 3 |
| Tablas SQLite reales | 44, no 53 |
| Integridad / FK check | `ok` / sin filas |
| Enforcement SQLite `foreign_keys` | 0 (desactivado por conexion) |
| Duplicados naturales en snapshot medido 02:55 UTC | 27 grupos |
| `normalized_key` duplicadas historicas | 169 grupos |
| Partidos futbol / FINISHED | 105 / 99 |
| Mapas LoL / team stats / player stats | 490 / 980 / 0 |
| Jugadores futbol / LoL | 0 / 0 |
| Recomendaciones ultimo run | 0 singles / 0 combos sobre 875 candidatos |
| Tests | 137 passed, 5 skipped, 30 warnings |
| Ruff / compileall / node check | 74 errores / OK / OK |

## A1. Identidad del despliegue

- Git host: `820a0393063a6af565e52ee0d0adc5f77730bb1a`, commit `Act8`, 2026-07-10 22:46:01 -03.
- Worktree previo a la auditoria: cambios en `main.py`, `events.py`, `pages.py`, `base.html`, `event_detail.html`, `test_aposta.py`; `docs/full-recovery.md` sin trackear. No se alteraron.
- `/api/info`: `build_commit=ab77f39`, timezone `America/Asuncion`. No coincide con Git.
- Imagen app `sha256:5fd1d4...`, creada 2026-07-10 23:45:34 -03; browser `sha256:8ee7d9...`, 22:05:26 -03. El worker corre con `sha256:9b2ee6...`, ya no disponible en el image store, y declara `BUILD_COMMIT=unknown`.
- App y worker tienen los mismos SHA256 para `worker_main.py`, `aposta_sync.py` y `sync/lol_sync.py`. Los siete archivos criticos host-contenedor comparados coinciden byte a byte.
- App y worker: mismo fingerprint de `DATABASE_URL` (`16e2e4683c86`), key de football configurada y `APP_TIMEZONE=America/Asuncion`. Ambos montan `/opt/pirapire/data:/app/data` y `/opt/pirapire/logs:/app/logs` RW.
- Estado: app healthy, browser healthy, worker sin healthcheck; los tres running, 0 restarts. Procesos unicos: Uvicorn, worker APScheduler y browser worker.
- Permisos: `.env` 0664 y SQLite 0644, ambos legibles por otros usuarios locales. `.env` no esta trackeado; `.env.example` si.

## A2. Eventos y aislamiento de odds

### Matriz vigente

| Public ID al corte | Deporte | Competicion | Equipos | Kickoff almacenado | Odds | Mercados API distintos | Matched | Mapped/unmapped |
|---:|---|---|---|---|---:|---:|---:|---:|
| 6755 | football | Internacional - Copa del Mundo | Noruega - Inglaterra | 2026-07-11 18:00 (naive local) | 5 | 2 | 5 | 5 / 0 |
| 6760 | football | Internacional - Copa del Mundo | Argentina - Suiza | 2026-07-11 22:00 (naive local) | 5 | 2 | 5 | 5 / 0 |
| 6765 | lol | Mid-Season Invitational | Hanwha Life Esports - Lyon Gaming | 2026-07-11 08:00+00:00 | 865 | 41 | 0 | 460 / 405 |

Prueba de aislamiento sobre el snapshot anterior (857): IDs 5023, 5028 y 5033 devolvieron 5, 5 y 847 selecciones; suma 857, interseccion logica vacia y cero labels de los otros matchups. `/api/events/4203` devolvio 404. El P0 hipotetico de 830 odds globales no se reprodujo.

La identidad usada por `/events/{id}` y `/api/events/{id}` es `ImportedOdds.id`. Cualquier odd del matchup sirve como ID, no solo la primera. El filtro usa `sport`, `team_a`, `team_b` y `competition`, pero omite kickoff, source event ID y bookmaker. No hubo colision actual con los mismos equipos/competicion en dos fechas, pero el codigo las mezclaria.

Los IDs expiran en cada `set_current_batch`: 5023/5028/5033 fueron 200 y, doce minutos despues, 404. El HTML oculta el error con 302 a `/`. `ApostaEvent.external_id` es artificial (`run-23-n`); 43 eventos, 9 identidades y los 43 con status `active`.

### Cambio de kickoff observado

| Batches | Noruega-Inglaterra | Argentina-Suiza |
|---|---|---|
| 9-12 | 2026-07-12 18:00 | 2026-07-12 22:00 |
| 13, despues de medianoche PY | 2026-07-11 18:00 | 2026-07-11 22:00 |

La fuente publica etiquetas `hoy/manana` segun Asuncion, pero `_parse_aposta_datetime` usa `datetime.utcnow()`. Antes de medianoche PY ya era el dia siguiente en UTC, por lo que `manana` sumaba un dia extra. Para LoL, Kambi entrega UTC y el dashboard corta el ISO sin convertir, luego agrega el literal `PY`: 08:00 UTC se muestra como 08:00 PY en vez de 05:00 PY.

## A3. Mercados y porcentajes

- Implied: 0 discrepancias en 7.629 `ApostaSelection`; la formula persistida es `1 / odds_decimal`. Muestras manuales football coinciden.
- No-vig football: los grupos 1X2 (3 outcomes) y O/U (2 outcomes) son matematicamente coherentes; ejemplo overround 9,44% y 9,89%.
- No-vig LoL: invalido. Se agrupa solo por `market_text|line|market_code`. Grupos observados: 11 de 2 outcomes, pero tambien grupos de 4, 6, 10, 15, 16, 20, 22, 24, 44, 46, 60 y 64 outcomes.
- Ejemplos: `Map 3 - Team Kills Handicap`, 64 selecciones, overround 3.343,88%; `Map 3 - Total Kills by the Player`, 60, overround 3.136,21%. La normalizacion fuerza que cada grupo sume 100%, pero mezcla lineas/jugadores incompatibles.
- 405/875 filas activas no tienen `market_id`, aunque todas tienen algun `market_code`. Hay falsos mappings: Odd/Even como total kills; deaths, minutos, torres e inhibidores como `total_maps_over_under`; Match Odds como `map_winner` sin catalog ID.
- No existen columnas `source_market_id` ni `source_outcome_id`. Los modelos tampoco guardan raw outcome label de forma separada.
- En el espejo mas reciente, 0/53 mercados tienen `period`, `map_number`, `player` o `role`. `line` esta poblado en 44, pero en LoL suele valer 1/2/3 por extraer `Map N`, no la linea del prop.
- `market_count` tiene tres significados incompatibles: API detalle cuenta grupos distintos (41), dashboard cuenta filas odds (865) y HTML server-side fija 0.

## A4. Fuentes y cobertura

La key de football esta configurada. Se realizo exactamente una consulta autenticada de auditoria a `/teams/770/matches?status=FINISHED&limit=10`: HTTP 200, 5 matches, filtro `limit=10`; el contrato esta soportado, pero el cliente actual no implementa ese metodo y sincroniza una ventana global de 45 dias.

| Fuente | Dato/prioridad | Estado real | Ultima evidencia | Error/limitacion |
|---|---|---|---|---|
| football-data.org | Fixtures/resultados, rank 90 | Activa | snapshots 2026-07-11 01:08 UTC | Solo 5 FINISHED por seleccion actual; cliente sin `/teams/{id}/matches`. Pacing 7s y un retry 429 correcto. |
| OpenLigaDB | Fallback, rank 85 | Catalogada | sin snapshot | No configurada (`shortcut/season` vacios). |
| StatsBomb Open Data | Historico, rank 90 | Catalogada | sin snapshot | No integrada al sync observado. |
| TheSportsDB | Metadata, rank 70 | Catalogada | sin snapshot | No integrada al sync observado. |
| Riot Data Dragon | Parches/campeones, rank 100 | Activa | 2026-07-09 21:48 UTC | Solo datos estaticos: 1 patch, 173 campeones. |
| Leaguepedia Cargo | Games/players, rank 85 | Parcial | games 2026-07-11 01:08 UTC | 490 mapas; players falla por funcion inexistente. Games limita 500 sin paginacion. Players no aplica `offset`. |
| Oracle's Elixir | Historico CSV, rank 85 | Manual | sin datos | 0 games/players Oracle; descarga automatica deshabilitada. |
| Kambi | Odds LoL | Activa | cada 12 min | TLS verification deshabilitado; IDs y dimensiones se descartan. |

`/sources` no publica ultima ejecucion/error; esos campos aparecen `null` aun cuando `sourcerunlog` contiene el fallo Leaguepedia. No hay matriz operacional unica persistida.

## A5. Calidad de base

`PRAGMA integrity_check` y `quick_check`: `ok`. `foreign_key_check`: sin violaciones actuales. Sin embargo, `PRAGMA foreign_keys=0`, por lo que nuevas escrituras no tienen enforcement. Se verificaron 0 huérfanos en imports/batches, catalogos, espejo Aposta, football teams y LoL team stats.

| Tabla | Filas | Tabla | Filas | Tabla | Filas | Tabla | Filas |
|---|---:|---|---:|---|---:|---|---:|
| apostaevent | 43 | apostamarket | 403 | apostaselection | 7.629 | apostasyncrun | 23 |
| betrecommendation | 7 | combohistory | 0 | comboleghistory | 0 | comborecommendation | 3 |
| comborecommendationleg | 6 | datasource | 11 | footballcompetition | 7 | footballmatch | 105 |
| footballplayer | 0 | footballstanding | 84 | footballteam | 84 | importedodds | 7.629 |
| lolchampion | 173 | loldatacoverage | 0 | lolgamehistory | 490 | lolleague | 17 |
| lolleaguealias | 37 | loloraclegame | 0 | loloracleplayerstat | 0 | lolpatch | 1 |
| lolplayergamestat | 0 | lolteamalias | 0 | lolteamgamestat | 980 | manualimportbatch | 13 |
| manualimporterror | 0 | marketalias | 56 | marketcatalog | 28 | marketsourcerequirement | 0 |
| match | 0 | normalizedentitymap | 0 | oddssnapshot | 0 | prediction | 0 |
| predictionhistory | 0 | rawsnapshot | 16 | recommendationrun | 21 | sourcecapability | 42 |
| sourcerun | 8 | sourcerunlog | 78 | sport | 3 | team | 0 |

16 tablas estan vacias. Varias pertenecen a APIs legacy aun expuestas (`sport`, `team`, `match`, `prediction`) y otras a flujos planeados no activos. `snapshot_id` es null en las odds, por lo que no se puede auditar contradiccion current/expired por snapshot persistido. En el snapshot activo todas las 875 filas pertenecen a un solo batch y son current.

Hardcodes confirmados: `lol_games=480` en dashboard pese a 490 en SQLite; texto dashboard llama “mercados” a filas odds; aliases de selecciones nacionales viven en codigo; el job de planteles contiene una key literal.

## A6. Ultimos 10 y estadisticas

| Participante actual | Unidad real | Cobertura n/10 | Periodo | Calidad |
|---|---|---:|---|---|
| Norway | partidos FINISHED | 5/10 | 2026 WC | GF 2,4; GA 1,8; UI no lo resuelve |
| England | partidos FINISHED | 5/10 | 2026 WC | GF 2,2; GA 1,0; UI no lo resuelve |
| Argentina | partidos FINISHED | 5/10 | 2026 WC | GF 2,8; GA 1,0; coincide con API |
| Switzerland | partidos FINISHED | 5/10 | 2026 WC | GF 2,6; GA 1,2; UI no lo resuelve |
| Hanwha Life Esports | mapas / series aproximadas | 10 mapas, ~3/10 series | 2026-07-03..09 | Solo W/L; stats numericas nulas |
| Lyon Gaming | mapas/series | 0/10 | n/a | Sin alias ni historial |

No hay servicio unico cross-sport de ventana 10. Football statistics carga hasta 50, procesa los primeros 10, pero reporta `matches=len(matches)`; no exige `status=FINISHED` ni `start_time < kickoff`. La traduccion busca equipos ingleses y luego consulta el mapa con el nombre espanol, causando 0 para Noruega/Inglaterra/Suiza.

LoL metrics ordena por `date`, pero el endpoint de evento ordena por `created_at` y limita 30 mapas. `LolGameHistory` tiene `game_number=NULL` en 490/490 y no tiene `series_id`; por tanto no puede formar ultimas 10 series. La fila 11 se conserva para equipos con mas de 10 mapas (por ejemplo T1 tiene 21), pero el requisito de series no es comprobable con el esquema actual.

## A7. Jugadores

| Deporte | Jugadores unicos | Filas stats | Cobertura participantes actuales |
|---|---:|---:|---|
| Futbol | 0 | 0 | 0/4 selecciones; sin posicion, dorsal ni fuente efectiva |
| LoL | 0 | 0 | 0/2 equipos; sin roster, rol, campeon, KDA, CS, oro o daño |

No se detectaron placeholders porque no hay filas. El worker de planteles no se ejecuta al arrancar, usa una key hardcodeada y solo queda programado cada 24 h. Leaguepedia players falla antes de importar. `lolteamalias` y `normalizedentitymap` estan vacias.

## A8. Predicciones y recomendaciones

- Modelo football: Poisson con decay, shrinkage y ajuste Dixon-Coles para 1X2/totales/BTTS/team totals/double chance. Con muestra efectiva menor a 30 se etiqueta `heuristic`, y esas filas son rechazadas por el recommender actual.
- LoL: winrate/promedios y una aproximacion determinista O/U; no es un modelo entrenado. Con los datos actuales no produce recomendaciones.
- Backtest 1X2: 10 predicciones, Brier 0,5579, accuracy 0,60, igual a baseline accuracy 0,60. No reporta baseline Brier ni log-loss.
- Backtest O/U 2.5: 10, Brier 0,2363 frente a baseline 0,21; accuracy 0,50; `validated=false`.
- Corte temporal walk-forward correcto en backtest, pero produccion ajusta el modelo con todos los `completed_matches` y no limita explicitamente a antes del kickoff evaluado.
- Ultimo run: 875 candidatos, 0 singles, 0 combos. Aceptar cero es la decision correcta.
- Persisten 7 recomendaciones antiguas con `coverage_status=model`, sin version de modelo ni estado de validacion; no pueden reproducirse con garantias.
- Las combinadas multiplican probabilidades y aplican una constante `0.97`, sin modelo/calibracion de correlacion. Solo se construyen desde top singles, pero no existe artefacto de validacion por mercado.

## A9. Workers y automatizacion

| Job | Horario real | Ultimas ejecuciones | Lock/retry | Observacion |
|---|---|---|---|---|
| Aposta | interval 12 min | 832, 832, 830, 857, 875; 24-40 s | `coalesce`, `max_instances=1`; sin retry propio | Cada run reemplaza IDs publicos y agrega espejo historico. |
| Deportes | interval 4 h, ejecutado al start | 8 sourceruns totales; ultimo football manual 49 s | mismo lock; HTTP transport 2 retries, 429 1 retry | `sync_if_stale` usa umbral 12 h; no hay trigger post-partido. |
| Planteles WC | interval 24 h | ninguna ejecucion observada | mismo lock; sin retry/telemetria SourceRun | No corre al start; key literal. |

No hay scheduler dentro de Uvicorn; un solo proceso worker. App y worker comparten DB/env. El worker no tiene healthcheck y los jobs no persisten proxima ejecucion, duracion ni filas para roster. Los errores se capturan y el scheduler considera el job “success”, aunque el trabajo interno falle.

## A10. API y rutas

OpenAPI contiene 67 paths/operaciones, todas unicas en el documento. Runtime advierte que `/api/info` esta registrado dos veces; OpenAPI oculta una de las dos implementaciones.

| Metodo | Rutas | Contrato 200 |
|---|---|---|
| GET | `/health`, `/api/info` | JSON |
| GET | `/sources`, `/sources/capabilities`, `/sources/rankings` | JSON |
| GET | `/source-runs`, `/{run_id}`, `/{run_id}/logs`, `/raw-snapshots` | JSON |
| GET | `/data/football/{competitions,teams,matches,standings,status}` | JSON |
| GET | `/data/lol/{patches,champions}` | JSON |
| GET | `/markets`, `/markets/aliases`, `/markets/{id}` | JSON |
| GET | `/imports/templates/{aposta-odds,oracles-elixir}` | archivo; OpenAPI lo declara JSON generico |
| GET | `/imports/batches`, `/{id}`, `/{id}/errors`, `/odds/imported` | JSON |
| GET | `/history/{predictions,combos}` | JSON |
| GET | `/lol-history/{status,leagues,coverage,team-metrics,player-metrics}` | JSON |
| GET | `/dashboard/{state,backtest,calendar}` | JSON |
| GET | `/aposta/{status,options,unmapped-markets,sync-runs,events,markets,selections}` | JSON |
| GET | `/api/events/{id}`, `/{id}/statistics` | JSON |
| GET | `/recommendations/{bets,combos,latest}` | JSON |
| POST | `/odds/analyze`, `/combo/analyze` | JSON |
| POST | `/sources/{seed,sync/*}`, `/markets/seed`, `/imports/*` | JSON/archivo upload |
| POST | `/history/*/settle`, `/lol-history/import*`, `/dashboard/refresh`, `/aposta/sync*`, `/recommendations/*` | JSON |

UI fuera de OpenAPI: `/`, `/sports/ui`, `/teams/ui`, `/matches/ui`, `/odds/ui`, `/combo/ui`, `/history/ui`, `/settings/ui`, `/sources/ui`, `/source-runs/ui`, `/data/football/ui`, `/data/lol/ui`, `/markets/ui`, `/imports/ui`, `/aposta/ui`, `/recommendations/ui`, `/events/{id}`.

Pruebas de contrato GET: 200 JSON correcto en `/api/info`; 404 JSON en market/event inexistente; 422 JSON para `run_id` no entero. No existe ningun 409 implementado. `/events/999999` devuelve 302 en vez de error. `/data/lol/upcoming` devuelve 404 aunque Equipos lo consume. No se hicieron POST contra el despliegue por modo read-only.

## A11. Frontend y UX

Playwright abrio dashboard, los tres eventos vigentes, futbol, LoL, equipos, historial, partidos y configuracion. El reloj fue visible y correcto en America/Asuncion. Dashboard no tuvo overflow en 375/768/1366/1920 y no presento spinners permanentes. En detalles no hubo errores de consola/red durante el primer corte.

Problemas reproducidos:

- Header de cada detalle muestra `1 cuotas - 0 mercados`; API/DOM muestran 5/2, 5/2 y 865/41.
- LoL muestra `7W undefinedD 3L`; Lyon desaparece por muestra 0.
- Noruega-Inglaterra muestra “Sin estadisticas disponibles”; Argentina muestra solo un equipo.
- Equipos solicita `/data/lol/upcoming` (404), lanza `events.forEach is not a function` y conserva `Cargando...`.
- Overflow movil: Futbol 723 px, LoL 579 px, Historial 995 px, Partidos 444 px y Settings 387 px sobre viewport 375.
- 0/3 event cards son focusables; usan `div onclick`. Dashboard contiene 4 handlers inline.
- Datos/API se interpolan en `innerHTML` en detalle, equipos, partidos y otros modulos sin escape, creando superficie XSS si una fuente controla labels.

Capturas:

- [Dashboard 375](audit-v2-captures/dashboard-375.png), [768](audit-v2-captures/dashboard-768.png), [1366](audit-v2-captures/dashboard-1366.png), [1920](audit-v2-captures/dashboard-1920.png)
- [Evento LoL](audit-v2-captures/event-lol-1366.png), [Noruega-Inglaterra](audit-v2-captures/event-norway-1366.png), [Argentina-Suiza](audit-v2-captures/event-argentina-1366.png)

## A12. Pruebas y seguridad

| Prueba | Resultado |
|---|---|
| `compileall` con pycache en `/tmp` | OK |
| `node --check app.js` | OK |
| `pytest -q`, sync externo deshabilitado, DB temporal | 137 passed, 5 skipped, 30 warnings |
| `ruff check app tests` | FAIL: 74 errores |
| Playwright determinista | No existe en suite; auditoria manual ejecutada |

Hay 142 funciones de test, pero 5 se saltan. Se contaron 57 asserts `status_code == 200`, 0 archivos que prueban `/api/events`, 0 que prueban no-vig/overround y el unico archivo que menciona Playwright verifica que no este en requirements. Los tests no habrian detectado IDs efimeros, mezcla por kickoff, header falso, 404 de Equipos o no-vig incompatible.

Seguridad: una key real esta literal en [`import_wc_squads.py`](../backend/app/services/import_wc_squads.py); no se reproduce en este informe. Kambi usa `CERT_NONE` y `check_hostname=False`. `.env` y DB tienen permisos demasiado amplios. El scan de logs no encontro patrones de bearer/key; `.env` no esta trackeado. Los dos archivos trackeados marcados por scan requieren rotacion/revision, empezando por el hardcode confirmado.

## Hallazgos completos

| ID | Sev. | Componente | Sintoma | Causa raiz | Evidencia | Archivos afectados | Datos afectados | Fix recomendado | Dependencias | Test de aceptacion |
|---|---|---|---|---|---|---|---|---|---|---|
| AUD-P0-001 | P0 | Fechas Aposta football | Kickoff salto de 12-Jul a 11-Jul al pasar medianoche PY | Parser resuelve `hoy/manana` con UTC | Batches 9-12 vs 13; lineas 11-42 parser | `aposta_html_parser.py` | Todos eventos relativos antes de medianoche | Resolver en `ZoneInfo(APP_TIMEZONE)`, persistir UTC aware y conservar raw | Identidad de evento | Fixture antes/despues de 00:00 PY produce el mismo instante UTC |
| AUD-P0-002 | P0 | Mercados/no-vig LoL | Probabilidades sin margen falsas; overround >3.300% | Se pierden jugador, linea, mapa y outcome ID; agrupacion por label/mapa | Grupos de 60/64 outcomes; 0 dimensiones | `kambi_lol_connector.py`, `models_imports.py`, `events.py` | 865 odds LoL activas | Modelo canonico por betOffer/criterion/outcome; no-vig solo grupo completo compatible | Migracion schema e identidad source | Suma no-vig=1 solo por `source_market_id`; props distintos nunca comparten grupo |
| AUD-P0-003 | P0 | Secretos/planteles | Credencial real versionada y desplegada | Key literal en codigo | Inspeccion de archivo y Git | `import_wc_squads.py` | Cuenta/API externa | Revocar, purgar historial cuando proceda, leer env y registrar solo presencia | Decision del propietario de credencial | Secret scan limpio; key antigua rechazada; job funciona con secret inyectado |
| AUD-P1-001 | P1 | Identidad publica | URLs pasan a 404 cada 12 min | URL usa `ImportedOdds.id`; batch anterior se marca no current | 5023/5028/5033: 200 y luego 404 | `pages.py`, `events.py`, `aposta_snapshot.py` | Todos enlaces/bookmarks | `event_key` estable y route por UUID/source identity; odds versionadas hijas | Migracion eventos | Misma URL responde mismo matchup tras dos syncs |
| AUD-P1-002 | P1 | Source identity | No existen `source_event_id`, market/outcome IDs; espejo duplica | Parser genera source URL pero normalizador/modelo la descarta; IDs `run-n` artificiales | 43 events/9 identidades, todos active | modelos Aposta/imports, parsers, sync | Historia y matching | Persistir IDs raw, unique constraints y upsert; expirar estado | P1-001 | Repetir payload no crea evento/mercado/outcome nuevo |
| AUD-P1-003 | P1 | Zona horaria LoL | 08:00 UTC se etiqueta 08:00 PY | UI corta ISO y concatena literal `PY` | Dashboard Playwright/API | `pages.py`, templates/JS datetime | Evento LoL actual | UTC aware end-to-end y formateo `America/Asuncion` | P1-001 | 08:00Z aparece 05:00 PY |
| AUD-P1-004 | P1 | Historico football | Solo 5/10 por seleccion; 3 equipos no resuelven en stats | Sync global 45d y bug en mapa espanol-ingles | GET team limit=10 soportado; SQLite 5/10 | football client/sync, `events.py` | 4 selecciones actuales | Backfill dirigido por team ID; alias persistido; cutoff kickoff | Fuentes e identidad | Cada seleccion devuelve 10 FINISHED anteriores al kickoff o n/10 explicito |
| AUD-P1-005 | P1 | Historico LoL | 10 mapas de Hanwha se presentan como partidos; Lyon 0 | Sin `series_id`; ventana por mapa/created_at; aliases vacios | 490 `game_number` null; 10 mapas ~3 series | models LoL, sync, metrics, events | Participantes MSI | Normalizar series/mapas, aliases, ordenar date, ventana 10 series | Leaguepedia/Oracle | 10 series con mapas asociados; 11a conservada fuera de ventana |
| AUD-P1-006 | P1 | Jugadores | 0 jugadores futbol y LoL | Roster no corre al start; Leaguepedia llama funcion inexistente | DB 0/0; log NameError | `worker_main.py`, `import_wc_squads.py`, `sync/lol_sync.py` | Todos participantes | Reparar conectores/paginacion y upsert temporal team-player | Secret y fuentes | Cobertura roster/roles/stats de todos equipos actuales |
| AUD-P1-007 | P1 | Frontend detalle | Header 1 cuota/0 mercados y stats parciales/undefined | Query server cuenta solo ID; market_count hardcoded; template asume draws LoL | Tres detalles Playwright | `pages.py`, `event_detail.html` | Todos eventos | Usar contrato evento estable, render states por deporte y n/10 | Identidad/stat service | Header=API; sin `undefined`; ambos equipos con estado explicito |
| AUD-P1-008 | P1 | Dashboard/conteos | UI dice 480 games y llama 865 odds “mercados” | Conteo hardcodeado y variable incrementada por fila | SQLite 490; dashboard Playwright | `pages.py`, `dashboard.html` | KPIs y eventos | Consultas DB y definiciones unicas de odds/mercados | Schema mercados | UI/API/SQLite coinciden |
| AUD-P1-009 | P1 | Equipos/UX | 404, JS exception y spinner permanente | Consume ruta inexistente `/data/lol/upcoming` | Playwright 375/1366 | `teams.html`, routers data | Vista Equipos LoL | Implementar contrato o cambiar consumidor; error/empty states | API identity | Sin 4xx/consola y loading termina |
| AUD-P1-010 | P1 | Seguridad transporte | Kambi acepta cualquier certificado | `CERT_NONE`, hostname off | Codigo conector | Odds LoL | TLS verificado, CA default, fallo cerrado y retry controlado | Ninguna | Cert invalido falla; endpoint real valida cadena |
| AUD-P1-011 | P1 | Modelos | No hay modelo validado que supere baseline; persisten 7 recs “model” | Backtest escaso, sin version/validacion persistida; LoL heuristico | 1X2 igual baseline; O/U peor | features, backtesting, recommendations models | Recomendaciones | Registry/version, cortes, Brier/log-loss y gates por mercado | Historicos completos | Solo mercados que superan baseline generan recs; cero permitido |
| AUD-P1-012 | P1 | Permisos | `.env` 0664 y DB 0644 | Umask/permisos de despliegue | `stat` host | Secretos y datos | 0600/0640 con usuario/grupo dedicado; contenedor no root | Decision operativa | Otro usuario no puede leer; app/worker si |
| AUD-P2-001 | P2 | Deployment | Git, `/api/info` y worker no identifican el mismo build | Build args/imagenes no atomicos | 820a039 vs ab77f39 vs unknown | Dockerfile/Compose/release | Trazabilidad | Etiqueta OCI y build commit unico; app+worker misma digest | Pipeline | `/api/info`, labels y Git release coinciden |
| AUD-P2-002 | P2 | DB | FK declaradas pero enforcement off; 16 tablas vacias/legacy | Engine SQLite sin PRAGMA y capas paralelas | PRAGMA=0; 44 tablas | `database.py`, modelos | Integridad futura | Habilitar FK por connection event; decidir tablas canonicas | Auditoria de migracion | Insercion huerfana falla; checks limpios |
| AUD-P2-003 | P2 | Duplicados/snapshots | Duplicados naturales y sin snapshot auditable | Key incluye batch/odds y `snapshot_id` no se llena | 27 grupos current, 169 key duplicates | sync/model imports | Historial odds | Snapshot entity, natural unique versionada y dedupe | Source IDs | Una selection por outcome/version; historial preservado |
| AUD-P2-004 | P2 | API | `/api/info` duplicada; HTML 302 oculta 404; no hay 409 | Routers superpuestos y contratos informales | Warning Uvicorn, GET contract | `main.py`, `health.py`, `pages.py` | Clientes/observabilidad | Router unico; 404 explicito; 409 para locks/conflictos | API versioning | OpenAPI/runtime sin duplicados; casos 200/404/409/422 |
| AUD-P2-005 | P2 | Responsive/a11y | Cinco vistas desbordan 375; cards no teclado | Tablas sin wrapper y `div onclick` | Playwright scrollWidth; 0 focusables | CSS/templates/JS | Usuarios movil/teclado | Scroll containers, anchors/buttons, focus/labels | API/UI fixes | Sin overflow de pagina; flujo completo teclado |
| AUD-P2-006 | P2 | XSS frontend | Labels remotos insertados con `innerHTML` | Construccion HTML por concatenacion | Grep templates/JS | Contenido de fuentes | `textContent`/DOM APIs o escape estricto; CSP | Ninguna | Payload HTML se muestra como texto; CSP test |
| AUD-P2-007 | P2 | Workers | Sin health worker ni telemetria uniforme; errores internos quedan job-success | Logging solamente y catches amplios | Compose/logs/source runs | Operacion | Health heartbeat, job_run por job, retry/backoff y errores propagados | DB job model | Ultimas 5 ejecuciones con duracion/filas/error; health degrada |
| AUD-P2-008 | P2 | Tests/calidad | Suite verde no cubre fallos productivos; ruff falla | Predominio status 200/fixtures superficiales | 57 asserts; 0 event/no-vig tests; 74 lint | tests/config lint | Confianza release | Tests contract/content, snapshot, Playwright determinista y lint gate | Fases P0/P1 | Cada bug tiene regresion; CI completa verde |
| AUD-P3-001 | P3 | Fuentes catalogo | `/sources` no refleja ultima actualizacion/error | Estado vive en logs/runs separados | Campos null pese a fallo conocido | source registry/router | Observabilidad | Vista materializada/matriz unificada | Worker telemetry | Fuente muestra prioridad, ultima ok y ultimo error reales |

## Blockers y decisiones del usuario

1. Revocar la credencial hardcodeada y decidir si se reescribe el historial Git. Es un blocker externo inmediato.
2. Confirmar el proveedor/cuenta canonica para IDs Aposta/Kambi y la politica de retencion de raw payloads.
3. Autorizar una migracion de identidad de evento/market/outcome y una ventana de mantenimiento con backup SQLite.
4. Elegir fuente historica LoL primaria: Oracle's Elixir real, Leaguepedia reparada o proveedor autorizado. Sin ella no se pueden validar jugadores/series/modelos.
5. Confirmar si football-data.org Tier One debe ser suficiente; la consulta muestra solo 5 partidos disponibles para England bajo los filtros/competiciones permitidos.

## Conclusion

El hotfix evita la mezcla global de odds, pero no resuelve la identidad del dominio. La prioridad no es ampliar modelos ni forzar recomendaciones: primero deben corregirse tiempo, source IDs, estructura de mercados/no-vig y secretos; despues historicos/jugadores; finalmente UX y validacion de modelos. El plan dependiente esta en [action-plan-v2.md](action-plan-v2.md).
