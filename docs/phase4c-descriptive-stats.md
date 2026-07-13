# Fase 4C — estadísticas descriptivas

## Objetivo

Materializar estadísticas descriptivas locales por evento y equipo a partir de datos ya validados: últimos 10 partidos football (ventana estricta por `event_key`) y últimas 5 series LoL complete anteriores al kickoff. Solo estadística descriptiva; sin predicciones, probabilidades, EV, recomendaciones, combinadas, simulaciones ni cambios de UI.

## Entradas

- `EventTeamHistoryWindow` (football), siempre por `event_key` y `cutoff_utc`; el partido ancla ya está excluido (Fase 4B41).
- `LolSeries` complete + mapas/jugadores Leaguepedia (`source_name='leaguepedia_map'`), siempre anteriores al kickoff del `event_key`.
- Datos crudos null-preserving existentes.

## Read-model y materialización

- Tabla `EventStatisticsReadModel(event_key, sport, status, input_fingerprint, payload_json, coverage_json, computed_at, updated_at)`.
- `input_fingerprint` = SHA1 de (event_key, kickoff, sport, equipos, y por football el conjunto de fixtures de la ventana + `updated_at`; por LoL el conjunto de series de la ventana + `updated_at`). Se recalcula **solo** si cambia el fingerprint.
- Lectura 100% local desde SQLite; cero llamadas externas durante requests.
- Idempotencia verificada: primera pasada recalcula, segunda pasada recalcula **0** (cache por fingerprint).

## Métricas football (por los 10 fixtures de la ventana, ancla excluido)

Promedios con cobertura `{non_null, denominator, required}`; `null` nunca es cero:
- Goles a favor/en contra; corners a favor; tiros y tiros a puerta a favor; faltas cometidas.
- Amarillas y rojas propias; tarjetas del rival mostradas como **recibidas por el rival** (sin atribución causal).
- HT y FT: W/D/L en cantidad y porcentaje con denominador de cobertura (HT suele ser parcial: solo partidos con HT publicado).
- Penaltis a favor/en contra: `awarded`, `scored` y `missed` por separado; nunca tandas.
- Jugador con más faltas: total, promedio por aparición y nº de partidos, **solo si la cobertura de faltas por jugador es completa** en la ventana; si es parcial → `status=incomplete`, `leader=null`.

## Métricas LoL (por mapas de las 5 series complete anteriores al kickoff)

- Últimas 5 series: fecha, rival, mapas y duración total de serie; detalle de las últimas 3.
- Por mapa (promedio + total de ventana): kills, muertes, torres e inhibidores del equipo. Las muertes se derivan de los kills del rival y se declaran `derived=true`.
- Promedio de kills totales del mapa = kills del equipo + kills del rival.
- Duración de mapa: promedio general, y separado en mapas ganados y perdidos.
- Por jugador: kills y muertes por mapa jugado; líder de kills de cada equipo y líder general del matchup.

## API

`GET /api/events/{event_key}/statistics` — solo lectura, sin red. Devuelve la respuesta separada por football/lol con `status`, `cutoff_utc`, `window`, cobertura por métrica y `_cache`. Si la cobertura es insuficiente devuelve `status=incomplete` con los datos disponibles; nunca inventa valores. No incluye odds ni campos de modelo.

## Índices (respaldados por EXPLAIN QUERY PLAN)

Antes: SCAN en `lolseries`; uso de índice mono-columna + TEMP B-TREE en la ventana. Después de añadir 7 índices compuestos, todas las consultas usan índice:

| Índice | Tabla | Columnas |
|---|---|---|
| ix_ethw_event_team_rank | eventteamhistorywindow | event_key, team, rank |
| ix_lgh_source_match | lolgamehistory | source_name, match_id |
| ix_ltgs_source_game | lolteamgamestat | source_name, source_game_id |
| ix_lpgs_source_game | lolplayergamestat | source_name, source_game_id |
| ix_esrm_event_sport | eventstatisticsreadmodel | event_key, sport |
| ix_lolseries_status | lolseries | series_status |
| ix_ffs_provider_source | footballfixturestat | provider, source_id |

`SELECT ... eventteamhistorywindow WHERE event_key=? AND team=? ORDER BY rank` → `SEARCH USING ix_ethw_event_team_rank` (sin TEMP B-TREE). `lolseries` → `SEARCH USING ix_lolseries_status` (sin SCAN).

## Resumen real

### Football — Argentina vs Suiza (`evt_0192…`, status complete)
- **Argentina** (ventana 10, ancla Suiza excluido): goles 2.8 a favor / 0.6 en contra, corners 4.7, faltas 12.44, amarillas 1.22, FT 10W-0D-0L; HT cobertura parcial 4/10; líder de faltas: **Cristian Romero**.
- **Suiza**: goles 2.2 / 1.3, corners 4.2; líder de faltas: **Rubén Vargas**.

### LoL — Hanwha Life Esports vs Lyon Gaming (`evt_803a…`, status incomplete)
- **Hanwha Life Esports**: 4 series complete anteriores al kickoff (la 5ª es posterior al kickoff → excluida por corte estricto), 14 mapas; kills/mapa 17.36, muertes/mapa 13.64 (`derived`), torres/mapa 7.5, kills totales de mapa 31.0, duración ganados 1804.8 s / perdidos 1898.75 s; líder de kills **Zeka**.
- **Lyon Gaming**: sin datos de mapa → `series_count=0`; el evento queda `incomplete` (sin valores inventados).

## Conteos

- Read-models materializados: **32** (10 football + 22 lol); 17 complete.
- Índices agregados: **7** (todos justificados por EXPLAIN QUERY PLAN).
- Idempotencia: 2ª ejecución recalcula 0.

## Validación

- `pytest` (sin `test_aposta*` de red y sin el pre-existente roto `test_phase0_containment.py`): **214 passed, 5 skipped, 0 failed**. 8 tests nuevos: media con denominador non_null, exclusión del ancla, null≠cero, W/D/L HT/FT con cobertura parcial, penaltis sin tandas, LoL 5 series/promedio por mapa/duración win-loss/líder de kills, player-leader bloqueado por cobertura incompleta, fingerprint sin recomputar, endpoint sin red.
- `ruff` de archivos tocados: correcto. `compileall`: correcto. `git diff --check`: limpio. `integrity_check=ok`.

## Stop

Detenido tras API y validación. No se modificó UI; la siguiente fase será optimización de consulta y UX.
