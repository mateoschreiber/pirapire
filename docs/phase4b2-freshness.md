# Fase 4B2 — frescura y completitud de series

## Objetivo

Completar los últimos 10 partidos reales por selección activa y las últimas 5 series reales por equipo LoL, marcando frescura y elegibilidad. No se calculan ni se muestran estadísticas.

## Precondiciones verificadas

- Backup `backups/phase4b2_20260711_235001/pirapire.db` (SHA-256 `c245e1adf16f5df4092cce11f2f592f1066acd7dee45d740b6d1a85d3b367064`) y `.env`.
- `integrity_check=ok`.
- Sin runs `running`/`pending` al iniciar.
- Invariantes de odds/snapshots intactos; todas las filas API-Football 2022-2024 (44 al inicio) preservadas.

## Cambios de esquema (migración idempotente)

Campos de calidad añadidos a `footballfixturestat`, `footballfixtureplayerstat` y `lolseries`:
`source`, `source_url`, `source_id`, `observed_at`, `data_as_of`, `freshness_class`, `eligible_for_last_n`. `lolseries` además guarda `game_ids_json`.

## Reglas aplicadas

- **Elegibilidad fútbol**: `eligible_for_last_n` marca exactamente los 10 FINISHED más recientes (por kickoff) anteriores al kickoff del evento Aposta.
- **Frescura fútbol**: los registros API-Football se marcan `historical_fallback_stale` cuando una fuente más reciente (TheSportsDB `eventslast`) demuestra un partido posterior. Ambas selecciones tienen un partido real 2026-07-07 (Mundial) que supera todo el histórico almacenado.
- **Penaltis**: los penaltis de tanda (`comments` con *shootout*) se excluyen; nunca cuentan como penaltis a favor/en contra.
- **null nunca es cero**: ni para equipo ni para jugador; los ceros solo se guardan cuando el proveedor publicó explícitamente un cero.
- **Serie LoL**: requiere `MatchId` confirmado y al menos un `GameId`. Las últimas 5 se ordenan por fecha de serie anterior al kickoff (no por cantidad de mapas).
- **Aliases**: se registran las resoluciones Aposta/Kambi -> Leaguepedia antes de usarlas; los ambiguos quedan pendientes.

## Reformulación de la consulta Leaguepedia

Antes (4B1) la consulta usaba una ventana de fechas corta y un filtro que dejaba fuera a los equipos de LRN. Ahora, por participante, se consulta `ScoreboardGames` buscando el nombre registrado en `Team1` OR `Team2`, `ORDER BY DateTime_UTC DESC`, sin filtro de liga ni ventana corta, recuperando `MatchId`, `GameId` y `N_GameInMatch`. Una consulta secuencial y espaciada por equipo dentro de la ventana permitida; ante 429 se persiste `Retry-After` o un cooldown de 6 h y se finaliza sin reintento.

## Adaptador de fallback por navegador (modo probe)

`browser_fallback.py` pide al worker interno renderizar páginas públicas y visibles con allowlist (`www.thesportsdb.com`). El worker expone `/render` que rinde una sola página por llamada, sin resolver CAPTCHA, sin login, sin paralelizar ni reintentar bloqueos. Probado: `render` de la página pública del equipo devuelve HTML (48 KB) y un host no permitido devuelve 403. No se usó para sobrescribir datos: la señal de frescura se obtuvo del API público de TheSportsDB.

## Fútbol — últimos 10 partidos por selección (elegibles, anteriores al kickoff)

Estado de todas las filas: `historical_fallback_stale` (superadas por el partido 2026-07-07). 40 filas de equipo (20 fixtures) + 709 filas de jugador, todas preservadas de 4B1.

### Argentina (10/10)
| Fecha UTC | Rival |
|---|---|
| 2024-07-15 00:30 | Colombia |
| 2024-07-10 00:00 | Canada |
| 2024-07-05 01:00 | Ecuador |
| 2024-06-30 00:00 | Peru |
| 2024-06-26 01:00 | Chile |
| 2024-06-21 00:00 | Canada |
| 2024-06-15 00:00 | Guatemala |
| 2024-06-09 23:00 | Ecuador |
| 2024-03-27 02:50 | Costa Rica |
| 2024-03-23 00:00 | El Salvador |

### Suiza (10/10)
| Fecha UTC | Rival |
|---|---|
| 2025-11-18 19:45 | Kosovo |
| 2025-11-15 19:45 | Sweden |
| 2025-10-13 18:45 | Slovenia |
| 2025-10-10 18:45 | Sweden |
| 2025-09-08 18:45 | Slovenia |
| 2025-09-05 18:45 | Kosovo |
| 2024-11-18 19:45 | Spain |
| 2024-11-15 19:45 | Serbia |
| 2024-10-15 18:45 | Denmark |
| 2024-10-12 18:45 | Serbia |

`most_recent_real` observado (TheSportsDB): Argentina 2026-07-07, Suiza 2026-07-07. Como ambos superan por >30 días todo el histórico API-Football, las 10 filas de cada selección quedan `historical_fallback_stale`.

## LoL — últimas 5 series por equipo (MatchId distinto, anteriores al kickoff)

167 series totales, 167 `MatchId` distintos. Cada serie tiene `MatchId` + ≥1 `GameId`.

### Bilibili Gaming (5/5) — kickoff 2026-07-12 08:00
2026-07-09, 2026-07-06, 2026-07-04, 2026-06-14, 2026-06-13

### Hanwha Life Esports (5/5) — kickoff 2026-07-12 08:00
2026-07-11, 2026-07-09, 2026-07-05, 2026-07-03, 2026-06-12

### NCG Esports (5/5) — kickoff 2026-07-12 19:00
2026-07-05, 2026-07-04, 2026-04-14, 2026-04-06, 2026-03-31

### Zeu5 Esports (5/5) — kickoff 2026-07-12 19:00
2026-07-05, 2026-07-04, 2026-05-19, 2026-05-05, 2026-04-21

### SDM Tigres (5/5) — kickoff 2026-07-12 19:00
2026-07-05, 2026-07-04, 2026-06-02, 2026-05-19, 2026-05-12

### Fuego (5/5) — kickoff 2026-07-12 19:00
2026-07-05, 2026-07-04, 2026-06-09, 2026-05-26, 2026-04-21

Leaguepedia cubrió LRN completamente, por lo que **no fue necesario recurrir a Liquipedia**.

## Matriz por campo (cobertura / fuente / frescura / elegibilidad)

| Dominio | Campo | Fuente | Frescura | Clasificación |
|---|---|---|---|---|
| Fútbol equipo | goals_for/against, HT | api_football | stale | stale |
| Fútbol equipo | corners, shots, shots_on_target, fouls, yellow_cards | api_football | stale | stale |
| Fútbol equipo | red_cards | api_football | — | absent (proveedor devolvió null) |
| Fútbol equipo | penalties_scored/missed (reglamentario) | api_football | stale | stale |
| Fútbol jugador | fouls, cards, penaltis | api_football | stale | Argentina: incompleto; Suiza: presente |
| LoL serie | MatchId, GameId, N_GameInMatch, fecha | leaguepedia | fresh | complete (6/6 equipos objetivo 5/5) |
| LoL serie | stats de mapa por serie | (pendiente) | — | absent |

`player_leader` fútbol: **bloqueado para Argentina** (faltan faltas por jugador en la ventana elegible), **computable para Suiza**. No se calcularon agregados.

## Validación

- Fútbol: cada lista elegible contiene exactamente los 10 partidos cronológicamente más recientes anteriores al kickoff (Argentina 10/10, Suiza 10/10).
- LoL: 5 `MatchId` distintos por equipo objetivo (Bilibili, HLE, NCG, Zeu5, SDM, Fuego), ordenados por fecha DESC anteriores al kickoff.
- Test: estadísticas 2022-2024 quedan `stale` porque existe historial reciente 2025-2026 (marca de frescura).
- Test: penaltis de tanda no se convierten en penaltis a favor/en contra.
- Test: `player_leader` bloqueado si faltan faltas en la ventana.
- Test: navegador usa allowlist y no duplica registros; series exigen MatchId+GameId; segunda pasada no cambia conteos (167 series, 167 MatchId, idempotente).
- `pytest` (sin `test_aposta*` de red externa y sin el pre-existente roto `test_phase0_containment.py`): **187 passed, 5 skipped, 0 failed**.
- `ruff` sobre archivos 4B2: correcto. `compileall`: correcto. `node --check`: correcto. `git diff --check`: limpio.

## Campos ya calculables vs bloqueados

**Calculables ahora (datos frescos, ventana completa):**
- LoL: existencia y composición de las últimas 5 series por MatchId para los 6 equipos objetivo (mapas por serie, resultado de serie), sin stats de mapa aún.

**Bloqueados:**
- Fútbol: todos los campos de equipo/jugador quedan `stale` — la ventana elegible se basa en datos 2022-2025 superados por el partido real 2026-07-07; falta una fuente de detalle 2026 (API-Football Free no cubre la temporada corriente; el fallback por navegador quedó en modo probe). No se calcula nada hasta contar con detalle reciente no stale.
- Fútbol `player_leader` (Argentina): bloqueado por faltas por jugador incompletas.
- LoL: estadísticas por mapa dentro de cada serie (kills, torres, etc.) siguen pendientes de vinculación por GameId.

## Stop

Ingesta y validación completas. No se iniciaron cálculos, API de estadísticas ni cambios de UI.
