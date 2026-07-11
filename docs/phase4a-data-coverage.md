# Fase 4A — gate de cobertura con datos reales

## Precondiciones y universo (2026-07-11 20:xx PY)

No había sync activa: el último run fue **134 success** (940 odds, 4 eventos, 0 errores). Invariantes Fase 3: 940 odds activas, 0 sin snapshot y un snapshot current para `aposta_la` y `kambi`.

| Deporte | Evento activo | Participantes | kickoff UTC |
|---|---|---|---|
| Fútbol | Copa del Mundo | Argentina, Suiza | 2026-07-12 01:00 |
| LoL | Mid-Season Invitational | Bilibili Gaming, Hanwha Life Esports | 2026-07-12 08:00 |
| LoL | LRN | NCG Esports, Zeu5 Esports | 2026-07-12 19:00 |
| LoL | LRN | SDM Tigres, Fuego | 2026-07-12 19:00 |

## Probes reales y aliases

- **TheSportsDB free key 123**: `searchteams(Argentina)` resolvió `idTeam=134509`; `eventslast` devolvió eventos terminados y `lookupeventstats(2513670)` devolvió tiros a puerta, tiros totales y otros stats de Argentina–Egipto. `fetched_at`: 2026-07-11; provider IDs conservables.
- **football-data.org**: conector y tablas existentes, pero no hay credencial API-Football configurable/activa. Datos locales: Argentina **5/10** finished; Suiza **0/10**. El gate no permite declarar cobertura de los últimos 10.
- **Leaguepedia Cargo**: probe HTTP para Bilibili Gaming recibió `ratelimited`; no se reintentó ni se usó Playwright. Los datos locales contienen mapas: BLG 12, HLE 15, NCG 5, Zeu5 5, SDM 6, Fuego 5; son mapas, no cinco series verificadas y completas.
- **Oracle's Elixir**: el proyecto solo ofrece import CSV local; no se encontró endpoint público accesible configurado. **Liquipedia/Riot/Data Dragon** no fueron usados para afirmar estadísticas de series.

## Matriz campo por campo

| Dominio/campo | Fuente mínima comprobada | Available | non-null / required | Estado |
|---|---|---:|---:|---|
| Fútbol kickoff, rival, local/visitante, FT, W/D/L | football-data + TheSportsDB | sí | Argentina 5/10; Suiza 0/10 | parcial |
| Fútbol competición y oficial/amistoso | TheSportsDB event metadata | sí | 1 probe / 10 por equipo | parcial |
| Fútbol HT, goles HT/FT | football-data para campos existentes | sí | insuficiente para 10/10 | parcial |
| Corners, amarillas, segundas/rojas | TheSportsDB event stats / lineup (a verificar por evento) | parcial | 0/20 auditados | ausente para gate |
| Tiros y tiros a puerta | TheSportsDB lookupeventstats | sí | 1/20 partidos requeridos | parcial |
| Faltas de equipo | TheSportsDB puede publicar stat, no garantizado | parcial | 0/20 auditados | ausente para gate |
| Faltas por jugador | ninguna evidencia de fuente gratuita | no | 0/20 | ausente |
| Penaltis de partido, sin tandas | ninguna normalización comprobada | no | 0/20 | ausente |
| LoL series_id y composición de 5 series | Leaguepedia Cargo | bloqueado por rate limit | 0/30 series | ausente |
| LoL game/map, fecha, torneo, equipos, ganador | datos locales Leaguepedia | sí por mapa | 5–15 mapas; 0/5 series confirmadas | parcial |
| LoL kills, muertes, torres, inhibidores, duración equipo | modelos/conector existentes; probe remoto bloqueado | parcial | no auditado en 5 series completas | parcial |
| LoL jugador/equipo/rol/kills/muertes | ScoreboardPlayers previsto; probe remoto bloqueado | parcial | no auditado en 5 series completas | parcial |

`null` no se trató como cero. No se infirieron corners, tiros, faltas ni penaltis del marcador. No hubo escritura en tablas deportivas, migración, cálculo ni UI.

## Conteo real por participante

| Participante | Requisito | Evidencia local encontrada | Gate |
|---|---:|---:|---|
| Argentina | 10 partidos | 5 FINISHED | 5/10 |
| Suiza | 10 partidos | 0 FINISHED | 0/10 |
| Bilibili Gaming | 5 series | 12 mapas | series no verificables |
| Hanwha Life Esports | 5 series | 15 mapas | series no verificables |
| NCG Esports | 5 series | 5 mapas | series no verificables |
| Zeu5 Esports | 5 series | 5 mapas | series no verificables |
| SDM Tigres | 5 series | 6 mapas | series no verificables |
| Fuego | 5 series | 5 mapas | series no verificables |

## Presupuesto y cadena recomendada

- Bootstrap fútbol: hasta 20 `eventslast`/fixture lookups + 20 stats + lineup solo donde haya tarjetas; con cache 24h y 2 s TheSportsDB: ~40–60 requests por ventana. No viable para campos por jugador/penaltis sin fuente adicional.
- Incremental cada hora: 2 equipos fútbol + 6 equipos LoL; 2–8 requests cuando cambie el calendario, cache TTL 60 min. Leaguepedia debe tener cuota/permiso recuperado antes de habilitarlo; no reintentar ante 429.
- Cadena mínima propuesta: football-data para identidad/resultados; TheSportsDB para stats publicados; **API-Football con credencial** o fuente equivalente comprobada para tarjetas/faltas/penaltis; Leaguepedia Cargo para LoL sólo tras acceso sostenible; Oracle CSV como fallback de ingestión verificable.

## Plan exclusivo para Fase 4B (no implementado)

1. Añadir tablas/campos de evidencia con provider, source_id, fetched_at y series→mapa; reutilizar `FootballMatch`, `LolGameHistory` y stats existentes, sin duplicar entidades.
2. Implementar ingesta idempotente limitada a participantes activos y sus ventanas n/10/n/5, con cache y backoff 429.
3. Persistir cobertura por campo como null-preserving evidence; separar tandas de penaltis.
4. Habilitar estadísticas derivadas sólo cuando la matriz alcance 10/10 fútbol o 5/5 series LoL completas; mantener los huecos explícitos.
