# Fase 4B — ingesta histórica

## Estado de ejecución

Precondiciones verificadas: SQLite `integrity_check=ok`, backup `backups/pirapire-phase4b-pre-ingestion-20260711.db`, 940 odds activas, cero sin snapshot y un snapshot current por feed. No había sync Aposta activa.

Se añadió un coordinador horario, de instancia única, que restringe siempre el universo a participantes de odds activas. API-Football figura como integración cifrada opcional; sin clave su estado es `unconfigured` y no realiza llamadas ni inventa cobertura. Leaguepedia mantiene el estado de acceso rate-limited de 4A y tampoco entra en bucles de reintento.

## Datos obtenidos / cobertura

No se descargó detalle nuevo: API-Football no tiene clave configurada y Leaguepedia Cargo estaba rate-limited. Los registros de ejecución dejan los participantes omitidos y la causa, sin escribir ceros ni alterar históricos. football-data/TheSportsDB y los modelos existentes siguen siendo reutilizables para la futura ingesta real.

## Idempotencia y siguiente acción

El coordinador es seguro sin proveedores accesibles: dos pasadas no crean matches, mapas ni jugadores. La ingesta real queda bloqueada por cobertura/acceso, no por una inferencia: configurar y probar API-Football, y esperar `Retry-After` de Leaguepedia antes de habilitar sus importadores paginados. No se implementaron agregados ni UI.
