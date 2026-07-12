# Fase 4B3 — hechos de mapa LoL y corrección de frescura football

## Objetivo

Vincular las últimas 5 series LoL confirmadas de cada participante activo con todos sus mapas y jugadores; corregir que los datos football `stale` nunca sean elegibles para cálculos. No se calculan ni se muestran estadísticas.

## Precondiciones verificadas

- Backup `backups/phase4b3_20260712_004954/pirapire.db` (SHA-256 `2ce1098ffc1856d7515d31be801bbc8ecb99e53953175922c675430c40f50efb`) y `.env`.
- `integrity_check=ok`.
- Sin runs `running`/`pending`.
- Odds, snapshots, datos football (44 filas) y las 167 series existentes intactas.

## Corrección de datos football

- Toda fila con `freshness_class=historical_fallback_stale` ahora tiene `eligible_for_last_n=false` (verificado: **0** filas stale elegibles).
- Se añadió `candidate_last_n=true` (40 filas) para indicar que la fila pertenecía a la mejor ventana disponible, sin presentarla como ventana actual.
- Argentina y Suiza: 10 candidatas cada una, 0 elegibles, 10 stale (superadas por el partido real 2026-07-07).

## Modelo y migración (idempotente)

- `footballfixturestat.candidate_last_n` (INTEGER).
- `lolseries.series_status` (`complete`/`partial`) y `lolseries.game_ids_json`.
- Hechos de mapa reutilizan `LolGameHistory`, `LolTeamGameStat` y `LolPlayerGameStat` con `source_name='leaguepedia_map'` para no colisionar con las filas del scoreboard previo (IDs hash).

## Ingesta de hechos de mapa

Para cada equipo activo se seleccionan sus 5 `LolSeries` más recientes con `MatchId` confirmado anteriores al kickoff (ventana candidata). Solo para esas series:

- **ScoreboardGames por MatchId**: persiste por mapa `MatchId`, `GameId`, `N_GameInMatch`, fecha, torneo, equipos, ganador, duración, kills, torres, inhibidores, dragones y barones de ambos lados. Las muertes por equipo se derivan de los kills del rival (Leaguepedia no publica un campo de muertes por equipo). null nunca se convierte en cero.
- **ScoreboardPlayers en lotes pequeños de GameId** (3 por consulta): persiste jugador, equipo, rol, kills, muertes, asistencias, CS y oro por mapa.
- Cada `GameId` se une a su `MatchId` exacto; nunca por cercanía de fecha o nombres.
- Cache persistente: los `GameId` ya almacenados no se vuelven a consultar. Consultas secuenciales y espaciadas; ante 429 se persiste `Retry-After`/cooldown 6h y se termina sin reintento en loop.

## Estado de serie

Una serie es `complete` solo si tiene resultado (todos los mapas almacenados tienen ganador) y todos sus `GameId` publicados están almacenados; de lo contrario `partial`. Solo las `complete` pueden entrar en la ventana de 5.

## Cobertura por equipo (6 objetivo, 5/5 series completas)

| Equipo | Series 5/5 | Mapas | team-map | player-map |
|---|---|---:|---:|---:|
| Bilibili Gaming | 5/5 | 20 | 40 | 200 |
| Hanwha Life Esports | 5/5 | 19 | 38 | 190 |
| NCG Esports | 5/5 | 13 | 26 | 130 |
| Zeu5 Esports | 5/5 | 15 | 30 | 150 |
| SDM Tigres | 5/5 | 17 | 34 | 170 |
| Fuego | 5/5 | 15 | 30 | 150 |

`player-map = mapas × 10` y `team-map = mapas × 2` exactos (sin duplicados).

### MatchId de las 5 series por equipo

- **Bilibili Gaming**: MSI Bracket Round 4_1, Round 2_2, Round 1_4; LPL Split 2 Playoffs Finals_1, Round 4_2.
- **Hanwha Life Esports**: MSI Bracket Round 4_2, Round 4_1, Round 2_1, Round 1_1; LCK Road to MSI Round 3_1.
- **NCG Esports**: LRN Split 2 Week 2_4, Week 1_3; Split 1 Week 6_4, Week 5_1, Week 4_2.
- **Zeu5 Esports**: LRN Split 2 Week 2_2, Week 1_4; Split 1 Playoffs Round 2_1, Round 1_3, Round 1_1.
- **SDM Tigres**: LRN Split 2 Week 2_3, Week 1_3; Split 1 Playoffs Round 3_2, Round 2_1, Round 1_4.
- **Fuego**: LRN Split 2 Week 2_2, Week 1_1; Split 1 Playoffs Finals_1, Round 3_1, Round 1_1.

## Conteos globales

- Mapas (leaguepedia_map): **98**.
- team-map stats: **196**.
- player-map stats: **980** (980 claves únicas).
- Series `complete`: **32**; series elegibles (flag): **27**.
- Football stale elegibles: **0**; football candidate: **40**.
- Cooldown Leaguepedia: ninguno (0 respuestas 429 durante la ingesta; ~72 consultas Cargo espaciadas 2 s).

## Worker

`run()` (horario) queda restringido a participantes activos: descubre series, arma la ventana candidata de 5 por equipo y solo consulta los `GameId` faltantes (cache). Con las series completas no vuelve a gastar consultas.

## Validación

- Test: stale football ⇒ `eligible_for_last_n=false`.
- Test: `GameId` sin `MatchId` no entra a una serie.
- Test: serie no `complete` si falta su resultado o alguno de sus mapas publicados; no elegible.
- Test: mapa persiste y deriva muertes de los kills del rival; sin duplicados de mapa/jugador en segunda pasada.
- Verificado para los 6 equipos: 5/5 series, mapas, filas team-map y player-map (arriba).
- Idempotencia: segunda sync no altera conteos (98/196/980/32/27) y `maps_new=0`, `games_queried=0` (cache).
- `pytest` (sin `test_aposta*` de red y sin el pre-existente roto `test_phase0_containment.py`): **193 passed, 5 skipped, 0 failed**.
- `ruff` sobre archivos 4B3: correcto. `compileall`: correcto. `node --check`: correcto. `git diff --check`: limpio.

## Stop

Cobertura completada y validada. No se iniciaron cálculos, API de estadísticas ni cambios de UI. No se intentó resolver el historial football 2025-2026 ni la Fase 4C.
