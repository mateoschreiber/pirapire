# Pirapire Full Recovery Report
**Date:** 2026-07-11
**Commit:** ab77f39 (Act7)
**Server:** 192.168.100.34 (cockpit)

## Executive Summary

Recuperación parcial completada. La sincronización Aposta.LA está activa y fluyendo 832 cuotas activas. Las rutas duplicadas fueron eliminadas. Los tests pasan 137/137. El backup R0 de 26.5 MB nunca fue persistido en disco — la recuperación de datos históricos depende de fuentes vivas.

---

## Phase A: Inventario y Rollback ✅

| Item | Valor |
|------|-------|
| Backup creado | `/opt/pirapire/backups/pirapire.db.fullrecovery_.bak` (2.1 MB) |
| PRAGMA integrity_check | ok |
| PRAGMA foreign_key_check | ok |
| Backup R0 (26.5 MB) | **NO EXISTE en disco** — nunca fue persistido |
| Backups disponibles | 4 DBs (0.4–1.9 MB), con datos limitados |
| Tablas activas | 53 tablas en la base actual |

### Baseline counts (pre-recovery)
| Métrica | Valor |
|---------|-------|
| importedodds (total/active) | 32 / 0 |
| footballmatch | 105 |
| footballplayer | 0 |
| footballteam | 84 |
| lolgamehistory | 490 |
| lolplayergamestat | 0 |
| lolteamgamestat | 980 |
| lolchampion | 173 |
| marketcatalog | 28 |

---

## Phase B: Recuperar Historial ⚠️ (limitado)

**Causa raíz:** El backup R0 de 26.5 MB documentado en `docs/recovery-progress.md` nunca existió como archivo en disco. Los backups disponibles contienen entre 0.4–1.9 MB sin datos de jugadores (footballplayer, lolplayergamestat). 

**Acción tomada:** No se puede recuperar historial de backup. La recuperación de jugadores y estadísticas debe venir de fuentes API vivas (football-data.org, Leaguepedia, DataDragon).

**Backups disponibles:**
```
pirapire.db..bak                  1.8 MB  (32 odds, 104 matches, 470 games, 173 champs)
pirapire.db.20260709_194413.bak   0.8 MB  (104 matches, 173 champs)
pirapire.db.20260709_191846.bak   0.8 MB  (104 matches, 48 teams, 173 champs)
pirapire.db.20260709_184703.bak   0.4 MB  (empty structure)
```

---

## Phase C: Corregir Identidad y Rutas ✅

### Fixes aplicados:

| Archivo | Cambio | Antes | Después |
|---------|--------|-------|---------|
| main.py:85-87 | events.router registrado 3x | 3 include_router | 1 include_router |
| events.py:175 | event_statistics duplicado | 2 definiciones | 1 definición |
| pages.py:240 | event_detail_page duplicado | 2 rutas idénticas | 1 ruta (matched_event_id) |

### Pendiente para Phase C completo:
- Crear `event_key` estable usando hash de fuente+deporte+equipos+kickoff
- Separar contratos HTML `/events/{key}` vs JSON `/api/events/{key}`
- Agregar `source_event_id`, `event_key`, `aposta_event_id` mediante migración
- Actualizar dashboard, calendario, detalle y estadísticas para usar event_key

---

## Phase D: Activar Fuentes Automáticas ✅ (parcial)

### Aposta.LA ✅

| Config | Antes | Después |
|--------|-------|---------|
| APOSTA_SYNC_MODE | csv_folder | **aposta_fetch** |
| Resultado sync | 0 odds | **832 odds** (10 football, 822 LoL) |
| Mercados mapeados | 0 | **472/832** |
| Mercados sin mapear | 0 | **360/832** |
| Worker automático | manual_required | **success cada 12min** |

### Football (football-data.org) ✅
- API key configurada en .env
- Worker sincroniza cada 4 horas
- 105 partidos de fútbol (7 competiciones: WC, CL, PL, BL1, SA, PD, FL1)
- Pendiente: sincronizar planteles y jugadores (WC squads endpoint)

### LoL (DataDragon) ✅
- 173 campeones importados
- 490 partidas de historial (Oracle's Elixir CSVs anteriores)
- 0 jugadores (sin datos de jugadores)
- Pendiente: Leaguepedia/Kambi para eventos y jugadores actuales

### LoL (Kambi) ⚠️
- 822 cuotas LoL importadas desde Aposta pero **sin matching a eventos** (matched_event_id = null)
- Se necesita el conector Kambi o el mapeo de eventos LoL

---

## Phase E: Fidelidad de Mercados ⚠️ (pendiente)

- 472/832 mercados mapeados al catálogo
- 360 mercados unmapped (necesitan clasificación)
- Pendiente: separar line/map_number/period/participant/player
- Pendiente: market_key y outcome_key estables
- Pendiente: nombres descriptivos en español

---

## Phase F: Últimos 10 y Estadísticas ⚠️ (pendiente)

- Sin footballplayer ni lolplayergamestat en la base
- Necesita importar datos históricos de football-data.org y Leaguepedia
- Las funciones get_last_completed_football/lol existen pero no tienen datos

---

## Phase G: Restaurar Navegación ⚠️ (pendiente)

- El menú actual tiene 6 enlaces que funcionan
- Las rutas antiguas de 16 enlaces necesitan redirects
- Los conteos del dashboard usan valores de la base (ya no hardcodeados)

---

## Phase H: Detalle y Dashboard ⚠️ (pendiente)

- event_detail.html renderiza pero con datos limitados (total_odds: 0)
- Necesita actualizarse para usar los 832 odds activos
- Las estadísticas requieren datos de jugadores (Phase F)

---

## Phase I: Recalcular y Verificar ⚠️ (pendiente)

- pytest: 137 passed, 0 failed ✅
- compileall: OK ✅
- node --check: OK ✅
- 3 contenedores healthy ✅
- Worker ejecuta Aposta cada 12min, Sports cada 4h ✅
- Pendiente: pruebas Playwright de todas las secciones
- Pendiente: despliegue final con BUILD_COMMIT

---

## Métricas Antes/Después

| Métrica | Antes (R0) | Después (R1C) | Ahora (Full Recovery) |
|---------|-----------|---------------|----------------------|
| active_odds | 0 | 0 | **832** |
| football_odds | 0 | 0 | **10** |
| lol_odds | 0 | 0 | **822** |
| football_match | 105 | 105 | 105 |
| football_player | 0 | 0 | 0 ⚠️ |
| lol_games | 490 | 490 | 490 |
| lol_players | 0 | 0 | 0 ⚠️ |
| aposta_sync_mode | csv_folder | csv_folder | **aposta_fetch** |
| routes duplicated | 3x events | 3x events | **0** |
| pytest failed | 8 | 0 | **0** |

---

## Próximos pasos críticos

1. **Importar jugadores de fútbol**: Activar `run_wc_squad_sync` para obtener planteles del Mundial desde football-data.org
2. **Conectar Kambi LoL**: Usar `kambi_lol_connector.py` para matchear los 822 odds LoL con eventos
3. **Importar datos LoL históricos**: Configurar Leaguepedia sync para team/player stats
4. **Recalcular recomendaciones**: Una vez con datos de features, ejecutar el motor de probabilidad
5. **Actualizar event_detail**: Usar los 832 odds activos en el detalle de eventos
6. **Capturas y despliegue final**: Playwright en 4 viewports, BUILD_COMMIT tag

---

## Rollback

```bash
# Volver al commit ab77f39 y restaurar base
cd /opt/pirapire
git checkout ab77f39
cp backups/pirapire.db.fullrecovery_.bak data/pirapire.db
BUILD_COMMIT=ab77f39 docker compose up -d --build pirapire_app pirapire_worker
```
