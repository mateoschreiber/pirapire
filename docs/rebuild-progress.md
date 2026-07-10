# Fase 2 — Captura Aposta.LA: Resumen

**Fecha:** 2026-07-10 13:50 UTC

---

## Resultados

### Mundial 2026 (fútbol)

| Indicador | Antes | Ahora |
|-----------|-------|-------|
| Cuotas totales vigentes | 296+ | **15** |
| Competiciones capturadas | 5+ (Club Friendly, Belarus, Brasil B, etc.) | **1 (Mundial)** |
| URL fuente | 6 endpoints | **1** (`/apuestas/deporte/1/4`) |
| Método | HTTP directo | HTTP directo |

**CONFIRMADO:** Solo se capturan cuotas del Mundial 2026. Las 15 cuotas corresponden a partidos del Mundial (España-Bélgica, Noruega-Inglaterra, Argentina-Suiza).

### League of Legends

| Indicador | Estado |
|-----------|--------|
| Método | Browser worker (Playwright) |
| Endpoint | `/snapshot?target=aposta_esports` |
| Resultado | **Timeout** — la SPA Angular de Aposta.LA no completa `networkidle` |
| Cuotas LoL capturadas | **0** |
| Causa raíz | `aposta.la/bets` es una SPA con WebSocket que nunca termina de cargar |

**NO_VERIFICADO:** Si Aposta.LA publica eventos LoL actualmente. El timeout impide confirmarlo.

---

## Cambios en código

| Archivo | Cambio |
|---------|--------|
| `config.py` | `aposta_fetch_urls` limitado a World Cup |
| `aposta_sync.py` | Agregado fallback browser-worker para LoL |
| `aposta_lol_parser.py` | **Nuevo** — parser para HTML de eSports (básico, detecta JSON/SPA patterns) |

---

## Problemas pendientes para Fase 3

1. **LoL no capturado:** Requiere ajustar el browser worker para esperar selectores específicos en lugar de `networkidle`.
2. **Solo 15 cuotas:** Con solo el Mundial, hay pocos candidatos para recomendaciones.
3. **Parser LoL básico:** Necesita mapeo real de la estructura JSON/HTML de Aposta.LA eSports.
4. **Sin eventos LoL confirmados:** No se sabe si Aposta.LA publica LoL actualmente.
