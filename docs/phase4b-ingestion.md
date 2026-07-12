# Fase 4B — ingesta histórica real (4B1)

## Precondiciones verificadas

- SQLite `integrity_check=ok`.
- Backup `backups/phase4b1_20260711_210114/pirapire.db` (SHA-256 `c2b08db75c399c5f2ddbb169dcddf043dabd32075b2391f194db6a02844ce443`) y `.env`.
- Invariantes de Fase 3: 940 odds activas, 0 sin snapshot, un snapshot current por feed (`Aposta.LA`).
- Sin runs `running`/`pending` al iniciar.
- API-Football configurada y validada desde Config (`status=success`, `source=ui`); TheSportsDB free v1 disponible.

## Participantes activos (universo de la ingesta)

- Fútbol: Argentina, Suiza.
- LoL: Bilibili Gaming, Hanwha Life Esports, NCG Esports, Zeu5 Esports, SDM Tigres, Fuego.

Toda consulta se restringe a estos participantes; ningún otro equipo se descarga.

## Arquitectura de la ingesta

Coordinador `historical_ingestion.run()`, horario, de instancia única, idempotente y acotado. No calcula, no predice, no toca frontend y nunca escribe ceros donde el proveedor no publicó un valor.

### API-Football (api-sports.io v3)

- Cliente nuevo `ApiFootballClient`: host fijo, header exclusivo `x-apisports-key` (nunca registrado), pacing configurable, tope de requests y un único reintento que respeta `Retry-After` en 429.
- Plan Free: no admite el parámetro `last` ni las temporadas 2025/2026; se usan las temporadas permitidas 2024/2023/2022 y se toman los últimos 10 fixtures FINISHED (`FT/AET/PEN`) por equipo, deduplicados por `fixture_id`, más recientes primero.
- Por cada fixture nuevo o incompleto se consultan `fixtures/statistics`, `fixtures/events` y `fixtures/players` una sola vez.
- Se persisten corners, tiros, tiros a puerta, faltas, tarjetas y penaltis de tiempo reglamentario por equipo (`FootballFixtureStat`) y faltas/tarjetas/penaltis por jugador (`FootballFixturePlayerStat`).
- Los penaltis de **tanda** se excluyen (eventos con `comments` que contiene *shootout*): nunca cuentan como penaltis a favor o en contra.
- Tope de 90 requests por bootstrap; al agotarse se persiste el cursor (`done_teams`/`pending`) y se continúa en la siguiente ventana. Un 429 real detiene el proveedor y deja el cursor.

### TheSportsDB (free v1)

- Se guarda inmediatamente la evidencia parcial disponible para partidos resueltos: `eventslast` + `lookupeventstats`, con `source_id`, fecha, equipos, cada estadística publicada, provider y `fetched_at`.
- Los campos no publicados quedan en `null`; no se exige 10/10 para persistir evidencia.
- No se trata como fuente de odds; solo complementa cuando el dato primario está ausente.

### Leaguepedia (Cargo)

- Se ejecuta solo si `next_retry_at` ya venció. Una única consulta paginada y lenta a `ScoreboardGames`.
- Se persiste `MatchId`, `GameId` y `N_GameInMatch`; los mapas se agrupan en una serie (`LolSeries`) únicamente por `MatchId` confirmado.
- Ante 429 o respuesta no-JSON (ratelimited), se actualiza `next_retry_at` (+6h) y se termina sin reintento.

## Modelos y migraciones (idempotentes)

- `FootballFixtureStat` (por equipo/lado, provider, `fixture_id`, `source_key` único, `fetched_at`, null-preserving).
- `FootballFixturePlayerStat` (faltas/tarjetas/tiros/penaltis por jugador, `source_key` único).
- `LolSeries` (serie confirmada por `MatchId`).
- Columnas nuevas idempotentes: `lolgamehistory.match_id`, `lolgamehistory.n_game_in_match`, `integrationproviderstate.next_retry_at`, `integrationproviderstate.cursor_json`.

## Datos obtenidos / cobertura real

| Proveedor | Estado | Requests | Filas | Cobertura |
|---|---|---:|---:|---|
| API-Football | success | 69 (bootstrap total) | 40 filas equipo + 709 jugador | 20 fixtures FINISHED |
| TheSportsDB | success | 6 | 4 filas evidencia | 2 eventos resueltos |
| Leaguepedia | success | 1 | 6 series | 6 series por MatchId |
| Riot API | unconfigured | 0 | 0 | omitido sin fallo global |

### Fútbol — n/10 por selección

| Selección | Fixtures FINISHED | Gate |
|---|---:|---|
| Argentina | 10/10 | completo |
| Suiza | 10/10 | completo |

Cobertura de campos (filas de equipo API-Football, 40 en total; el resto queda `null`, nunca cero):

| Campo | non-null |
|---|---:|
| goals_for / ht_goals_for | 40/40 |
| corners | 32/40 |
| shots_total | 32/40 |
| shots_on_target | 32/40 |
| fouls | 32/40 |
| yellow_cards | 32/40 |
| red_cards | 0/40 (proveedor no publicó valor; se conserva null) |
| penalties_scored (reglamentario) | 32/40 |
| penalties_missed (reglamentario) | 32/40 |

Faltas por jugador: 709 filas; `fouls_committed` 223/709, `fouls_drawn` 205/709 (solo donde el proveedor publicó); tarjetas y penaltis 709/709.

### LoL — n/5 series

| Equipo | Series confirmadas (MatchId) |
|---|---:|
| Bilibili Gaming | 3 |
| Hanwha Life Esports | 4 |
| NCG Esports | 0 |
| Zeu5 Esports | 0 |
| SDM Tigres | 0 |
| Fuego | 0 |

6 series totales, todas con `MatchId` único. Las series de LRN (NCG, Zeu5, SDM, Fuego) no aparecieron en la ventana de Leaguepedia; los huecos quedan explícitos, sin inventar cobertura.

## Idempotencia

Dos pasadas adicionales (`RUN_B`, `RUN_C`) tras el bootstrap no cambiaron ningún conteo: 40 filas de equipo (20 fixtures), 709 filas de jugador (709 claves únicas), 6 series (6 `MatchId` únicos). API-Football hizo 0 requests en las repasadas (cursor con ambos equipos completos) y Leaguepedia no creó series nuevas. `fixture_id` es único por proveedor/lado vía `source_key`; `GameId`/serie requieren `MatchId` confirmado.

## Cursor pendiente

- API-Football: `{"done_teams": ["Argentina", "Suiza"], "pending": []}` — bootstrap de fútbol completo.
- Leaguepedia: `next_retry_at=null` (sin bloqueo activo).

## Worker incremental

`run()` sigue programado cada hora (`historical-ingestion`). Se limita a participantes activos y solo trae detalles faltantes o partidos/series recién finalizados; con el cursor completo no vuelve a gastar requests. En el entorno de tests la ingesta en vivo se desactiva con `PHASE4B_LIVE_INGESTION=false` para no depender de la red.

## Validación

- `pytest` (sin los módulos con dependencia de red externa `test_aposta*` y sin el pre-existente `test_phase0_containment.py`, roto desde antes de esta fase por un import inexistente): **180 passed, 5 skipped, 0 failed**.
- Suite específica: `test_phase4b1_ingestion` (8) y `test_phase4b_ingestion` (2) en verde.
- `ruff` sobre todos los archivos tocados en 4B1: correcto.
- `compileall`: correcto. `node --check`: correcto. `git diff --check`: limpio.

## Bloqueo restante

- LoL LRN: sin series confirmadas en la ventana Leaguepedia consultada; se resolverá cuando Leaguepedia publique los `MatchId` correspondientes.
- API-Football Free: sin temporada corriente (solo 2022–2024); la cobertura n/10 usa los últimos partidos disponibles en ese rango.
