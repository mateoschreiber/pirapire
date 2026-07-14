# Fase 4D1 — ciclo de vida de eventos y refresco incremental

## Objetivo

Mostrar solo encuentros futuros reales de Aposta.LA y actualizar datos locales únicamente cuando la sincronización detecte eventos, participantes u horarios nuevos/modificados.

## Modelos y migración (idempotente)

- `apostaevent.local_event_state` (TEXT, indexado) — estado del evento: `scheduled`, `live`, `finished`, `unknown_time`, `stale`.
- `apostaevent.last_reconciled_at` (TIMESTAMP) — última reconciliación.
- Tabla `RefreshQueue` — cola coalescida por `event_key` con lock de instancia y TTL de 600 s.

## Derivación de estado local

`event_lifecycle.derive_state()` clasifica cada evento:

| Estado | Condición |
|---|---|
| `scheduled` | Kickoff futuro, snapshot activo y odds vigentes |
| `live` | Kickoff en las últimas 4 horas |
| `finished` | Kickoff hace más de 4 h o `ApostaEvent.status='expired'` |
| `unknown_time` | Kickoff ausente pero snapshot vigente |
| `stale` | Sin snapshot vigente o sin odds activas |

Los eventos `scheduled` son los únicos que se muestran como Próximos. `finished` e `historical` permanecen almacenados pero no se presentan como próximos. `unknown_time` se almacena sin mostrarse.

## Reconciliación post-sync

`event_lifecycle.reconcile_after_sync()` se ejecuta al final de cada sync exitoso de Aposta. Compara los `event_key` del snapshot nuevo con el anterior y calcula el diff (added/removed/changed). Para cada evento nuevo o cambiado deriva su estado y lo escribe. Para los removidos los marca como `stale`. La reconciliación de snapshots es **atómica**: un sync parcial/fallido no inactiva eventos existentes; solo un snapshot completo lo hace.

## Cola de refresco coalescida

`refresh_queue.enqueue()` hace upsert por `event_key` — varios syncs antes del worker pisan la misma fila con el estado más reciente. Solo se encolan eventos `added` o `changed`; los `removed` solo se inactivan. Un lock de instancia (10 min TTL) impide workers concurrentes; expirados se liberan automáticamente.

## Dashboard

La ruta `GET /` ahora consulta exclusivamente eventos `scheduled` desde `ApostaEvent.local_event_state`, en lugar de depender solo de `ImportedOdds.is_current`. Se eliminó el fallback hardcodeado de eventos WC expirados (Argentina, Noruega, etc.). La verificación: Argentina vs Suiza queda `stale` (sin snapshot vigente) y NO aparece en el dashboard.

## Worker incremental

Nuevo job `run_event_refresh` cada 15 minutos (coalesce, max_instances=1):

1. `event_lifecycle.refresh_states()` — regenera estados de todos los eventos desde el snapshot vigente.
2. `refresh_queue.enqueue_scheduled_events()` — encola eventos `scheduled` cuyo `last_reconciled_at` supera el TTL de 1 h.
3. Procesa hasta 5 tareas: para cada una toma lock, verifica que el evento siga `scheduled`, lo refresca (`compute_event` por fingerprint) y libera.

## Conteos (en DB desplegada)

- Eventos totales: 452 (430 stale, 22 scheduled, 0 finished).
- Refresh queue: 0 (se llena en cada sync Aposta; el worker lo procesa).

## Validación

- Argentina vs Suiza (evento WC expirado): `local_event_state=stale` → **no aparece** en el dashboard.
- Solo eventos `scheduled` (22) tienen odds vigentes y kickoff futuro.
- Test de estados (7 casos), refresh queue coalescencia + lock + TTL (2 casos), derive_state para todos los escenarios.
- Invariantes: `null` no toca odds, snapshots, football, LoL, read-models ni ventanas históricas.
- Idempotencia: fingerprint cache del read-model evita recomputación innecesaria. TTL de 1 h en la cola evita refrescos repetidos.
- `pytest` (sin `test_aposta*` de red y sin el pre-existente roto `test_phase0_containment.py`): **224 passed, 5 skipped, 0 failed**. 10 tests nuevos de fase 4D1.
- `ruff` de archivos tocados: correcto. `compileall`: correcto. `git diff --check`: limpio.

## Stop

Validado ciclo de vida y refresco incremental. No se modificó UI.
