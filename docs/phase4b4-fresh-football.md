# Fase 4B4 — datos frescos de fútbol

## Objetivo

Obtener y almacenar los últimos 10 partidos realmente más recientes de cada selección presente en próximos eventos de fútbol de Aposta.LA, con estadísticas descriptivas frescas. No se calculan promedios ni se modifica la UI.

## Alcance dinámico (sin hardcodear)

El snapshot Aposta.LA actual no tenía eventos de fútbol `is_current`. Por decisión del usuario, cuando no hay fútbol activo se ancla dinámicamente a los eventos de Mundial **más recientes del historial de odds** como alcance temporal, sin modificar `is_current` ni presentarlos como próximos. Alcance resuelto: **Argentina, Suiza, Noruega, Inglaterra** (kickoffs 2026-07-12).

## Fuentes y orden (probe-first)

Se hicieron probes antes de implementar:

1. **football-data.org** (`get_team_matches`, credencial ya aceptada): entrega la lista de partidos WC recientes y HT/FT autoritativos, pero **sin** estadísticas descriptivas y solo 6 partidos WC (plan free). Se usa para verificación cruzada de HT.
2. **API-Football / TheSportsDB**: API-Football free no cubre 2025-2026; TheSportsDB free devuelve 1 solo evento. Insuficientes para la ventana.
3. **SofaScore vía browser worker** (páginas públicas visibles, allowlist explícita, una página a la vez, sin CAPTCHA/login/evasión): un Chromium real abre la página pública del equipo y lee sus propios datos públicos: últimos 30 eventos, estadísticas por partido (corners, tiros, tiros a puerta, faltas, tarjetas), incidentes (penaltis de tiempo reglamentario, excluyendo tandas) y faltas por jugador. Es la fuente que completa la ventana de 10 con estadísticas.

No se usaron APIs privadas, CAPTCHA, evasión de bloqueos ni scraping paralelo.

## Modelo y migración (idempotente)

- `footballfixturestat.penalties_awarded` y `footballfixturestat.match_type` (official/friendly) añadidos.
- Filas frescas con `provider='fresh_football'`, `source='sofascore'`, `source_id`, `source_url`, `observed_at`, `data_as_of`, `fetched_at`, `freshness_class='fresh'`.
- `eligible_for_last_n` / `candidate_last_n` marcan exactamente los 10 más recientes anteriores al kickoff.

## Ventana de 10 partidos por selección (elegibles, anteriores al kickoff)

40 filas de equipo elegibles (10 × 4), 106 filas totales, 1.378 filas de jugador. Todas las filas frescas; ninguna stale es elegible.

### Argentina (10/10) — vs, resultado, tipo
2026-07-12 Switzerland 3-1 (oficial) · 2026-07-07 Egypt 3-2 (of.) · 2026-07-03 Cabo Verde 3-2 (of.) · 2026-06-28 Jordan 3-1 (of.) · 2026-06-22 Austria 2-0 (of.) · 2026-06-17 Algeria 3-0 (of.) · 2026-06-10 Iceland 3-0 (amistoso) · 2026-06-07 Honduras 2-0 (am.) · 2026-03-31 Zambia 5-0 (am.) · 2026-03-27 Mauritania 2-1 (am.)

### Suiza (10/10)
2026-07-12 Argentina 1-3 (of.) · 2026-07-07 Colombia 4-3 (of.) · 2026-07-03 Algeria 2-0 (of.) · 2026-06-24 Canada 2-1 (of.) · 2026-06-18 Bosnia 4-1 (of.) · 2026-06-13 Qatar 1-1 (of.) · 2026-06-06 Australia 1-1 (am.) · 2026-05-31 Jordan 4-1 (am.) · 2026-03-31 Norway 0-0 (am.) · 2026-03-27 Germany 3-4 (am.)

### Noruega (10/10)
2026-07-11 England 1-2 (of.) · 2026-07-05 Brazil 2-1 (of.) · 2026-06-30 Côte d'Ivoire 2-1 (of.) · 2026-06-26 France 1-4 (of.) · 2026-06-23 Senegal 3-2 (of.) · 2026-06-16 Iraq 4-1 (of.) · 2026-06-07 Morocco 1-1 (am.) · 2026-06-01 Sweden 3-1 (am.) · 2026-03-31 Switzerland 0-0 (am.) · 2026-03-27 Netherlands 1-2 (am.)

### Inglaterra (10/10)
2026-07-11 Norway 2-1 (of.) · 2026-07-06 Mexico 3-2 (of.) · 2026-07-01 DR Congo 2-1 (of.) · 2026-06-27 Panama 2-0 (of.) · 2026-06-23 Ghana 0-0 (of.) · 2026-06-17 Croatia 4-2 (of.) · 2026-06-10 Costa Rica 3-0 (am.) · 2026-06-06 New Zealand 1-0 (am.) · 2026-03-31 Japan 0-1 (am.) · 2026-03-27 Uruguay 1-1 (am.)

Evidencia de que no se omite un partido posterior: el partido más reciente almacenado por selección coincide con su último FINISHED anterior al kickoff (Argentina/Suiza 2026-07-12 01:00; Noruega/Inglaterra 2026-07-11 21:00).

## Matriz por campo (non_null/10)

| Campo | Argentina | Suiza | Noruega | Inglaterra |
|---|---|---|---|---|
| goals_for/against | 10 | 10 | 10 | 10 |
| ht_goals (via football-data) | 5 | 6 | 5 | 5 |
| corners | 10 | 10 | 10 | 10 |
| shots_total | 10 | 10 | 10 | 10 |
| shots_on_target | 10 | 10 | 10 | 10 |
| fouls | 10 | 10 | 10 | 10 |
| yellow_cards | 9 | 7 | 8 | 8 |
| red_cards | 1 | 2 | 0 | 1 |
| penalties_awarded | 10 | 10 | 10 | 10 |
| penalties_scored | 10 | 10 | 10 | 10 |
| penalties_missed | 10 | 10 | 10 | 10 |
| faltas por jugador (fixtures) | 10/10 | 10/10 | 10/10 | 10/10 |

`null` nunca se guarda como cero: `red_cards`/`yellow_cards` quedan null cuando SofaScore no publica el stat (p. ej. algunos amistosos). Cada métrica conserva su propia cobertura n/10. `penalties_awarded` se guarda aparte de `scored`/`missed`; las tandas se excluyen.

## Fuentes, requests y navegaciones

- football-data.org: 1 request cacheado (lista de equipos WC) + hasta 4 (uno por equipo) en la primera pasada.
- SofaScore browser worker: 1 navegación de búsqueda + 1 navegación de equipo por selección (secuencial, una página a la vez); cada navegación lee 14 eventos + stats/incidentes/lineups desde la misma página pública.
- Sin 429 observados. No se usó SofaScore raw (403 sin navegador); el navegador es un Chromium real sobre la página pública.

## Idempotencia y caché

- Upsert null-preserving por `source_key` (`fresh_football|<fixture>|<side>`); jugador por `fresh_football|<fixture>|<pid>|<nombre>`. Segunda ejecución: filas 106→106, elegibles 40→40, jugadores 1.378→1.378 (sin duplicados).
- Caché de ventana: si una selección ya tiene 10 filas elegibles con stats antes del kickoff, se **omite la re-descarga** completa (segunda pasada: `finished_seen=None`, 0 navegaciones SofaScore, ~40 s frente a ~4 min). El worker horario solo busca partidos nuevos y completa campos null.

## Worker

Nuevo job horario `fresh-football` en `worker_main.py`. El fetch de red se hace fuera de una transacción de escritura y la persistencia usa commits cortos, de modo que el SQLite de un solo escritor nunca queda bloqueado durante las navegaciones lentas.

## Invariantes verificadas

- `null` nunca es cero (test).
- Ninguna fila stale tiene `eligible_for_last_n=true` (0 en DB; test).
- No se calculan promedios/porcentajes/líderes/predicciones ni se toca la UI.
- Sin duplicados por `source_key`.
- Odds/snapshots/LoL con los mismos conteos (odds_current=292; lol_map_games=98; lol_player_map=980).

## Validación

- Backup e `integrity_check=ok` antes (`backups/phase4b4_20260712_192214/`, SHA-256 `35c2baf0…`) y después (`ok`).
- Tests de ventana deslizante (entra el nuevo, sale el más antiguo), null, tandas, frescura, deduplicación y caché.
- `pytest` (sin `test_aposta*` de red externa y sin el pre-existente roto `test_phase0_containment.py`): **202 passed, 5 skipped, 0 failed**.
- 9 tests nuevos en `test_phase4b4_fresh_football.py`.
- `ruff` sobre archivos tocados: correcto. `compileall`: correcto. `git diff --check`: limpio.

## Bloqueo restante

Ninguno para el alcance actual: las 4 selecciones tienen sus 10 partidos recientes comprobados con estadísticas. HT (`ht_goals`) queda parcial (5-6/10) porque football-data solo publica HT de partidos WC; SofaScore expone HT por `period1` y podría completarse en una iteración futura si se requiere.

## Stop

Datos almacenados y validados. No se iniciaron promedios, optimización global de SQLite ni cambios de UI.
