# Recuperación — Fase 0

Fecha: 2026-07-11 (America/Asuncion)

Estado: **bloqueada antes del despliegue por falta de rotación de la credencial expuesta**.

## Resumen ejecutivo

Se implementaron y probaron las contenciones de credenciales, TLS, no-vig y horarios. No se modificaron históricos, jugadores ni modelos predictivos. No se ejecutó sync ni despliegue porque la clave configurada sigue siendo la expuesta y todavía autentica.

Estado enmascarado de Football Data:

- `configured=true`
- `value=********`
- `rotated_value_differs=false`
- credencial expuesta: `HTTP 200` (todavía válida)
- credencial nueva: no probada; no existe un valor rotado distinto en `.env`

Acción humana obligatoria antes de continuar:

1. Revocar la credencial expuesta.
2. Crear una credencial nueva.
3. Escribirla directamente en `/opt/pirapire/.env` como `FOOTBALL_DATA_API_KEY`, sin copiarla a prompts, logs ni documentación.

## 0.1 — Credenciales

- Se eliminó la credencial literal de `backend/app/services/import_wc_squads.py`.
- El importador usa exclusivamente `settings.football_data_api_key` y falla cerrado si no está configurada.
- App y worker leerán el mismo `/opt/pirapire/.env`, montado como `/run/secrets/pirapire.env:ro`.
- Se retiró `env_file` de Compose para impedir que el secreto aparezca en `docker inspect Config.Env` tras el despliegue.
- Las copias antiguas `backups/.env*.bak` que contenían la credencial expuesta fueron eliminadas.
- Escaneo del worktree por el literal expuesto: una única coincidencia, `.env` (pendiente de rotación).
- Imagen aislada de prueba: sin coincidencia del literal en metadata o contenido de aplicación.
- Logs actuales (últimas 500 líneas de los tres contenedores): sin coincidencias de la credencial.
- `/api/info`: solo publica `app`, `build_commit`, `docs`, `env`, `health` y `timezone`; no publica secretos.

## 0.2 — Historial Git

La credencial fue enviada a `origin/main`. Commits afectados:

- `0b63ed757c7d7295490f38d43b039cca0b5959f4`
- `820a0393063a6af565e52ee0d0adc5f77730bb1a`
- `ab77f390dad36f25fb14c1fed86f5ed8052973b7`
- `88dbb820118ad2497a99b1813bd481ae061e8ed1`

No se reescribió historial ni se hizo force-push. La limpieza remota requiere autorización explícita y no sustituye la rotación.

## 0.3 — TLS Kambi

- Eliminados `CERT_NONE` y `check_hostname=false`.
- Se usa `ssl.create_default_context()` con validación de CA y hostname.
- Timeout por defecto: 25 segundos; un único retry acotado para timeout/errores de transporte.
- Los errores de certificado se propagan inmediatamente, sin retry ni fallback inseguro.
- Petición real controlada: `kambi_tls_verified=true`, payload JSON válido, 2 eventos observados.
- Prueba de certificado inválido: rechazado en el primer intento.

## 0.4 — Permisos

- `.env`: `0600 mateo:mateo`.
- `data/pirapire.db`: `0640 mateo:mateo`.
- Archivos de `backups/`: `0640`.
- Directorios `data/` y `backups/`: `0750`.
- No se cambiaron propietarios: los contenedores actuales ejecutan como root y podrán leer los bind mounts; la comprobación final queda ligada al despliegue.
- Otros usuarios locales no tienen bits de lectura sobre `.env`.

## 0.5 — Contención no-vig

- LoL: no-vig deshabilitado aunque el grupo tenga dos outcomes.
- La cuota decimal permanece visible.
- `implied_probability` permanece como `1 / cuota`.
- La API y la UI exponen: `No disponible: mercado pendiente de normalización.`
- Football: no-vig solo se calcula para grupos completos exactos de 3 outcomes en 1X2 y 2 outcomes en O/U identificado.
- Grupos incompletos o con outcomes adicionales no se normalizan.
- Forecasts, recomendaciones y combinadas no consumen ningún campo no-vig.
- No se reactiva no-vig LoL antes de Fase 3.

## 0.6 — Horarios

- “Hoy” y “mañana” se resuelven usando la fecha de `America/Asuncion`.
- El resultado local se convierte una sola vez a UTC para almacenamiento.
- Los conectores conservan `event_date_raw` y `event_time_status` para auditoría futura.
- Kambi conserva el timestamp UTC raw y la UI lo convierte a America/Asuncion.
- Registros existentes sin raw/status quedan `unconfirmed` y se muestran como `Horario pendiente de reconfirmación`.

Ejemplos antes/después observados en la base actual:

| Deporte | Antes | Después del despliegue |
|---|---|---|
| football | `2026-07-11T18:00:00` | Horario pendiente de reconfirmación |
| football | `2026-07-11T22:00:00` | Horario pendiente de reconfirmación |
| LoL | `2026-07-12T08:00:00+00:00` | Horario pendiente de reconfirmación hasta nuevo sync |

Conversión verificada para dato confirmado Kambi: `08:00 UTC → 05:00 PY`.

Pruebas de borde verificadas:

- 23:59 PY + “mañana 00:01” → 03:01 UTC del día siguiente.
- 00:01 PY + “hoy 00:01” → 03:01 UTC del mismo día local.

## 0.7 — Backup, imagen y operación

Backup consistente creado antes de cualquier despliegue:

- Archivo: `backups/pirapire.db.phase0_20260711_111517.bak`
- SHA-256: `aa516ca7dd5214628631905bfd659d38787adf9cc5c0f1d4b1ad69e5f6457219`
- Base origen: `PRAGMA integrity_check=ok`
- Backup: `PRAGMA integrity_check=ok`
- Ensayo de rollback: restauración temporal correcta, `integrity_check=ok`, 44 tablas.

Compose quedó preparado para construir una sola imagen `pirapire_app` y reutilizarla en app y worker. Se agregó healthcheck al worker.

No ejecutado por la precondición incumplida:

- commit final;
- despliegue de app y worker;
- migración aditiva de metadata de horarios;
- sync controlado;
- prueba de la nueva credencial;
- comprobación final de misma digest/build commit;
- comprobación final de tres contenedores healthy.

Los contenedores en ejecución siguen siendo la versión anterior: app healthy, browser healthy y worker running sin healthcheck; app y worker aún no comparten digest.

## Verificación ejecutada

- `pytest`: **145 passed, 5 skipped, 0 failed**.
- `compileall`: correcto.
- `ruff` sobre archivos modificados: correcto.
- `node --check backend/app/static/js/app.js`: correcto.
- `git diff --check`: correcto.
- TLS Kambi real: correcto.
- Certificado inválido: rechazado.
- Backup y restore drill: correctos.

## Criterio para desbloquear

Después de que el usuario rote la clave directamente en `.env`, ejecutar exactamente una petición controlada con la nueva clave y verificar que la anterior devuelve rechazo. Solo entonces crear el commit final, construir/desplegar la imagen única, ejecutar un sync controlado y cerrar las verificaciones operativas.

## Fase 0B — Contraste y accesibilidad del dashboard

Estado visual: **implementado y verificado en previsualización aislada; pendiente de despliegue por la misma compuerta de rotación**.

### Tema y tarjetas

- Se reutilizan exclusivamente las variables canónicas existentes: `--surface`, `--surface-2`, `--text`, `--text-muted`, `--border` y `--accent`.
- Eliminado el fallback inexistente `var(--card-bg, #fff)`.
- Eliminados los colores hardcodeados de textos del dashboard V3.
- `event-card` usa `--surface`, texto principal `--text`, metadata `--text-muted` y borde `--border`.
- Hover usa `--surface-2` y borde `--accent`.
- Focus visible usa outline `3px solid var(--accent)` con offset de 2 px.
- El indicador F/L mantiene fondo `--accent` y texto blanco.
- En móvil equipos y metadata se apilan, admiten wrapping y mantienen altura mínima de 64 px.

### HTML y teclado

- Las tarjetas pasaron de `div onclick` a enlaces `<a href="/events/{id}">`.
- Toda la superficie es activable.
- El ID actual se conserva sin modificar identidad ni conteos.
- Cada enlace tiene `aria-label` con equipos, competición, horario y cantidad de mercados.
- Prueba Playwright: foco alcanzado mediante Tab, outline visible de 3 px y Enter solicitó correctamente `/events/33816`.

### Contraste medido

| Tema | Equipos / superficie | Metadata / superficie |
|---|---:|---:|
| light | 15.62:1 | 5.43:1 |
| dark | 13.51:1 | 6.61:1 |

El indicador/focus activo supera 3:1 contra su superficie. Títulos, competición, horario, cantidad de mercados y mensajes vacíos heredan `--text` o `--text-muted`; no hay texto blanco sobre fondo blanco.

### Playwright y responsive

Se probaron light y dark a 375, 768, 1366 y 1920 px:

- estilos computados de tarjeta/equipos/metadata correctos en los ocho escenarios;
- `event-card` computado como elemento `A`, `display:flex`, `min-height:64px`;
- cero overflow horizontal global;
- cero errores de consola y cero `pageerror`;
- navegación por teclado correcta;
- revisión visual manual de móvil y escritorio correcta.

Capturas:

- `docs/phase0b-captures/dashboard-light-375.png`
- `docs/phase0b-captures/dashboard-light-768.png`
- `docs/phase0b-captures/dashboard-light-1366.png`
- `docs/phase0b-captures/dashboard-light-1920.png`
- `docs/phase0b-captures/dashboard-dark-375.png`
- `docs/phase0b-captures/dashboard-dark-768.png`
- `docs/phase0b-captures/dashboard-dark-1366.png`
- `docs/phase0b-captures/dashboard-dark-1920.png`

### Integridad de eventos

La previsualización se ejecutó sobre una copia del backup, sin `.env` y sin sync. Antes y después del arranque conservó exactamente 708 cuotas actuales y 3 identidades actuales. No se modificó la base productiva.

El duplicado solicitado queda documentado para Fase 2, sin corregirlo en este parche:

- Argentina–Suiza, Copa del Mundo, `2026-07-11T22:00:00` (285 filas históricas/odds agrupadas en la base actual).
- Argentina–Suiza, Copa del Mundo, `2026-07-12T22:00:00` (40 filas históricas/odds agrupadas en la base actual).

### Verificación técnica 0B

- `pytest`: **146 passed, 5 skipped, 0 failed**.
- `compileall`: correcto.
- `ruff` sobre archivos modificados: correcto.
- `node --check backend/app/static/js/app.js`: correcto.
- `git diff --check`: correcto.

### Compuerta de cierre

Comprobación enmascarada al finalizar 0B:

- `configured=true`
- `value=********`
- `rotated_value_differs=false`
- confirmación del usuario recibida: no

Por lo tanto siguen bloqueados el commit final, despliegue, petición con credenciales, sync y healthchecks finales. Los contenedores productivos continúan sin cambios.

## Actualización Fase 0C

El gestor cifrado de integraciones y el parche visual fueron desplegados con el commit `1772622008d43733eb98e88f46e34dda7a3be031`. App, worker y browser están healthy; app y worker comparten la digest `sha256:8e9d21077af95216344204a8a96b7f5d9a3e1ef75b2be4f85e1213f003020748`.

Football sync queda bloqueado mientras la fuente efectiva no sea un override UI probado. La invocación de control cerró con 0 inserts, 0 updates y ninguna petición externa. La Fase 0 aún no se cierra: el usuario debe revocar la clave expuesta, crear una nueva e ingresarla directamente en Config. Después se eliminará el fallback antiguo de `.env` y se ejecutará el sync final.
