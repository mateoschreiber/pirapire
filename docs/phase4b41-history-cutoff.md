# Fase 4B41 — corte histórico estricto por evento

## Objetivo

Corregir la selección de últimos 10 para que un evento nunca use su propio partido ni datos posteriores a su kickoff. Solo ventanas históricas de fútbol; sin descargar fuentes, navegar, modificar datos crudos, UI, LoL, odds ni cálculos.

## Causa del defecto (4B4)

La ventana de 4B4 marcaba `eligible_for_last_n` usando el kickoff más reciente re-listado del equipo (Argentina vs Suiza aparecía re-listado a las 22:00), por lo que el propio partido ancla (Argentina vs Suiza @ 01:00) quedaba incluido en su propia ventana.

## Corrección

- Nueva relación `EventTeamHistoryWindow(event_key, team, fixture_source_id, rank, cutoff_utc, opponent, kickoff_utc, source_key)`.
- Se identifica cada evento ancla por `event_key`, `kickoff_utc` y participantes.
- Para cada equipo del evento se seleccionan exactamente 10 fixtures FINISHED con `kickoff_utc` estrictamente menor que `cutoff_utc` (= kickoff del evento).
- Se excluye siempre el fixture ancla: mismo rival que el otro participante del evento y kickoff dentro de ±2 días del cutoff (cubre diferencias de formato/re-listado horario), además del corte estricto `< cutoff`.
- La vacante dejada por el ancla se completa con el siguiente partido más antiguo disponible (rank 10 retrocede hasta 2025 cuando corresponde).
- El partido ancla se conserva en datos crudos (`footballfixturestat`) y puede formar parte de la ventana de un evento posterior, nunca de la suya.
- Las ventanas por evento se consultan por `event_key` (relación `EventTeamHistoryWindow`), no con `eligible_for_last_n` global.

Módulo `event_history_window.build_windows(session)` es puro de datos, idempotente (borra y reconstruye) y se ejecuta al final de `fresh_football.run()`.

## Ventanas corregidas — primer y décimo partido por equipo

Cutoff = kickoff del evento. El ancla (Argentina vs Suiza / Noruega vs Inglaterra) queda excluido de su propia ventana.

### Evento Argentina vs Suiza (cutoff 2026-07-12)
- **Argentina (10)**: rank 1 = 2026-07-07 vs Egypt … rank 10 = 2025-11-14 vs Angola.
- **Suiza (10)**: rank 1 = 2026-07-07 vs Colombia … rank 10 = 2025-11-18 vs Kosovo.

### Evento Noruega vs Inglaterra (cutoff 2026-07-12 / 07-11)
- **Noruega (10)**: rank 1 = 2026-07-05 vs Brazil … rank 10 = 2025-11-16 vs Italy.
- **Inglaterra (10)**: rank 1 = 2026-07-06 vs Mexico … rank 10 = 2025-11-16 vs Albania.

En las 3 re-listas de cada matchup (Argentina vs Suiza a 07-12 22:00, 07-12 01:00, 07-11 22:00; Noruega vs Inglaterra a 07-12 18:00, 07-11 21:00, 07-11 18:00) el ancla queda excluido y cada lado conserva 10 filas rank 1..10 con `kickoff_utc < cutoff_utc`.

## Validación

- Argentina vs Suiza **no aparece** en la ventana histórica de ese mismo evento (verificado en las 3 re-listas).
- Noruega vs Inglaterra **no aparece** en la ventana histórica de ese mismo evento.
- Cada lado conserva 10 filas con `rank` 1..10 y `kickoff_utc < cutoff_utc` (0 filas con kickoff ≥ cutoff; máx. 10 por evento/equipo).
- Un evento posterior distinto puede incluir el partido ancla ya finalizado si es anterior a su propio kickoff (test `test_anchor_available_for_a_later_event`).
- Conteos sin cambios: odds_current=292, fresh_fixtures=106, fresh_players=1378, lol_map_games=98, lol_player_map=980.
- `event_windows_total`=120, 6 eventos con ventana (2 matchups × 3 re-listas × 2 equipos × 10).
- `integrity_check=ok` antes y después.
- Tests nuevos (`test_phase4b41_history_cutoff.py`): 4 passed. `ruff` de cambios: correcto. `compileall`: correcto. `git diff --check`: limpio.

## Stop

Corregido y validado. No se calcularon promedios.
