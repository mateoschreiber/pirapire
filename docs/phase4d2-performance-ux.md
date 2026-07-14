# Fase 4D2 — rendimiento del dashboard y UX

## Objetivo

Eliminar la lentitud del dashboard usando exclusivamente datos locales.

## Diagnóstico (baseline)

Antes de la intervención el dashboard sufría `database is locked` durante las escrituras del worker (sync Aposta cada 12 min), porque:

- **Journal mode: `delete`** — SQLite bloquea lectores mientras hay un escritor activo.
- **Query no optimizada**: `SELECT * FROM importedodds` cargaba 80+ columnas para luego hacer deduplicación en Python; además hacía múltiples queries separadas (odds count, scheduled keys, events, recommendations, lol players).
- **Sin índice compuesto** en la ruta de join `ImportedOdds.event_key + ApostaEvent.event_key` para el filtro `local_event_state='scheduled'`.

## Cambios aplicados

### 1. WAL journal mode
`PRAGMA journal_mode=WAL` permite lecturas concurrentes durante escrituras. Agregado a `integration_migrations.run_migrations()` para persistir en cada rebuild.

### 2. Índices para la ruta caliente del dashboard
- `ix_odds_event_key_current ON importedodds(event_key, source_name, is_current)` — permite SEARCH en el JOIN con ApostaEvent.
- `ix_apostaevent_scheduled ON apostaevent(local_event_state, event_key)` — COVERING INDEX para el filtro de scheduled.

### 3. Optimización de la consulta del dashboard
Reemplazado el flujo de 3 queries + dedup Python por un solo JOIN con agregación SQL:

```sql
SELECT ie.event_key, ie.team_a, ie.team_b, ie.competition,
       ie.kickoff_utc, ie.event_date_sort, ie.sport,
       ie.event_time_status,
       COUNT(*) AS market_count, MIN(ie.id) AS event_id
FROM importedodds ie
JOIN apostaevent ae ON ie.event_key = ae.event_key
WHERE ie.source_name='aposta_la' AND ie.is_current=1
  AND ae.local_event_state='scheduled' AND ae.event_key IS NOT NULL
GROUP BY ie.event_key, ie.team_a, ie.team_b, ie.competition,
         ie.kickoff_utc, ie.event_date_sort, ie.sport,
         ie.event_time_status
ORDER BY ie.kickoff_utc IS NULL, ie.kickoff_utc, ie.event_date_sort
LIMIT 30
```

EXPLAIN QUERY PLAN antes: SCAN en importedodds + TEMP B-TREE. Después: SEARCH en ambos índices.

Tiempo de la consulta en caliente: **~0.4 ms**.

### 4. Eliminación de subqueries innecesarias
- `RecommendationRun` y `BetRecommendation` ya no se consultan en el dashboard.
- `LolPlayerGameStat` ya no se consulta en el dashboard (usa conteo materializado desde `_dashboard_counts`).

## Medición post-optimización

- Dashboard HTTP: **200 OK** estable bajo carga.
- Sin errores `database is locked` observados después de WAL.
- Test suite: **224 passed, 5 skipped, 0 failed**.

## Pendiente para UI (siguiente iteración)

La modernización visual de cards, event detail con estadísticas del read-model y los mercados con etiquetas descriptivas queda pendiente de un ciclo de desarrollo con acceso gráfico para validar responsive, contraste y navegación por teclado. La infraestructura de datos ya está optimizada.

## Verificación

- `integrity_check=ok`
- WAL mode: `wal`
- BUILD_COMMIT: `9eac3f54...`, imagen `sha256:3b50b3c...`
- 3 contenedores healthy, dashboard 200.
