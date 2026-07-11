# Recuperación — Fase 0C

Fecha: 2026-07-11 (America/Asuncion)

Estado: gestor implementado y desplegado; bootstrap bloqueado de forma segura hasta recibir una credencial distinta de la heredada del entorno.

## Arquitectura implementada

### Catálogo fijo

El catálogo vive en código y no acepta URLs, conectores ni proveedores creados desde la UI.

| Proveedor | Credencial | Prueba fija | Capacidades |
|---|---|---|---|
| Football-data.org | `api_key` | endpoint fijo de competición WC | fixtures, resultados, tablas, equipos |
| Riot API | `api_key` | endpoint fijo de estado NA1 | cuentas y partidas no profesionales |
| TheSportsDB | `api_key` | búsqueda fija de equipo | metadata, equipos, eventos |
| Aposta / Kambi | No requiere clave | — | cuotas y mercados |
| Leaguepedia | No requiere clave | — | calendario, equipos, jugadores, histórico |
| Data Dragon | No requiere clave | — | parches, campeones, items, assets |
| Oracle's Elixir | No requiere clave | — | CSV histórico y estadísticas |

### Almacén cifrado

- Tabla idempotente `integrationcredential` con proveedor, nombre, valor cifrado, last4, fechas, estado de prueba y último uso.
- Tabla `integrationaudit` con proveedor, operación, fecha, resultado, actor y código sanitizado.
- Cifrado autenticado Fernet.
- Clave maestra externa: `/app/data/secrets/integration-master.key`.
- Secreto bootstrap: `/app/data/secrets/config-admin.password`.
- Clave de sesión: `/app/data/secrets/config-session.key`.
- Directorio con modo `0700`; archivos con modo `0600`, propietario compatible con app/worker.
- Ninguno de esos archivos entra en la imagen, Git o SQLite.
- Sin la clave maestra correcta, los overrides cifrados no pueden recuperarse; el error es controlado.

### Resolución dinámica

`SecretProvider` resuelve en cada job, sin caché de proceso:

1. override UI con prueba exitosa;
2. fallback de entorno;
3. no configurada.

App y worker comparten SQLite y `/app/data`, por lo que una rotación exitosa será visible en el siguiente job sin reiniciar contenedores. Football-data y el importador de planteles ya consultan este proveedor al comenzar cada ejecución.

Mientras `football_sync_ui_bootstrap_required=true`, todo sync de football queda bloqueado si la fuente efectiva no es `ui`. Esto impide utilizar la credencial expuesta del entorno durante el bootstrap.

## Autenticación y API

- Sesión administrativa limitada a `/api/settings`.
- Cookie HttpOnly, SameSite=Strict, con Secure cuando el esquema es HTTPS.
- CSRF firmado y comprobación de Origin en escrituras.
- Rate limiting por IP para login y pruebas.
- Password bootstrap y claves de sesión fuera de Git/SQLite.
- Credenciales recibidas con tipos secretos y nunca incluidas en respuestas o auditoría.

Endpoints:

- `GET /api/settings/integrations`
- `POST /api/settings/integrations/{provider}/test`
- `PUT /api/settings/integrations/{provider}/credentials/{name}`
- `DELETE /api/settings/integrations/{provider}/credentials/{name}`

Una rotación prueba primero el candidato en memoria. Solo una prueba exitosa cifra y reemplaza dentro de un commit; una prueba fallida conserva la credencial funcional anterior. DELETE elimina únicamente el override e informa si vuelve al entorno.

## Interfaz Config

- Login administrativo separado.
- Una card por proveedor.
- Inputs secretos vacíos con `autocomplete=new-password`.
- Nunca se precarga un valor guardado en el DOM.
- Fuente efectiva, terminación enmascarada, última prueba, último uso y error sanitizado.
- Acciones Probar, Guardar nueva y Eliminar override con confirmación.
- Proveedores públicos marcados “No requiere API key”.
- Diseño responsive y compatible con light/dark.

Capturas:

- `docs/phase0c-captures/config-light-375.png`
- `docs/phase0c-captures/config-light-768.png`
- `docs/phase0c-captures/config-light-1366.png`
- `docs/phase0c-captures/config-light-1920.png`
- `docs/phase0c-captures/config-dark-375.png`
- `docs/phase0c-captures/config-dark-768.png`
- `docs/phase0c-captures/config-dark-1366.png`
- `docs/phase0c-captures/config-dark-1920.png`

## Evidencia de seguridad

- Lecturas y escrituras anónimas: rechazadas.
- Password incorrecto: rechazado.
- CSRF ausente o inválido: rechazado.
- Origin externo: rechazado.
- Rate limit de login: verificado.
- Candidato inválido: no reemplaza el override vigente.
- Rotación válida sintética: ciphertext distinto del secreto; lectura dinámica inmediata.
- Concurrencia worker/rotación: lectores observan el valor anterior o el nuevo, nunca un estado parcial.
- GET, HTML y respuestas de escritura: no contienen el secreto.
- SQLite: no contiene el secreto sintético en texto plano.
- Auditoría: no contiene el secreto ni request bodies.
- Clave maestra incorrecta: HTTP 409 sanitizado y `credential_decryption_failed`.
- Archivos runtime: `0600`; clave maestra ausente de SQLite.

## Staging visual y técnico

- 7 proveedores visibles; 3 inputs secretos y 4 proveedores sin clave.
- Inputs secretos vacíos en los ocho escenarios.
- Light/dark a 375, 768, 1366 y 1920 px.
- Contraste de texto principal: 15.62:1 light y 13.51:1 dark.
- Contraste secundario: 5.43:1 light y 6.61:1 dark.
- Sin overflow horizontal.
- Consola y `pageerror`: cero errores.
- `pytest`: **162 passed, 5 skipped, 0 failed**.
- `ruff`: correcto.
- `compileall`: correcto.
- `node --check`: correcto.
- `git diff --check`: correcto.

## Secuencia operativa pendiente

1. Desplegar app/worker con el gestor y football sync bloqueado.
2. El usuario revoca la credencial antigua.
3. El usuario crea una nueva credencial e ingresa por Config usando el secreto bootstrap local.
4. La app prueba y guarda el override cifrado.
5. Eliminar el valor antiguo de `.env` sin imprimirlo.
6. Confirmar `source=ui` y ejecutar un sync controlado.
7. Escanear SQLite, logs, inspect, HTML y artefactos.

La clave maestra debe respaldarse por separado junto con SQLite. Un backup de SQLite sin su clave maestra no permite recuperar las credenciales cifradas.

## Despliegue de bootstrap

Desplegado el commit `1772622008d43733eb98e88f46e34dda7a3be031` sin borrar volúmenes.

- Imagen app/worker: `sha256:8e9d21077af95216344204a8a96b7f5d9a3e1ef75b2be4f85e1213f003020748`.
- App y worker: misma digest.
- App: healthy.
- Worker: healthy.
- Browser: healthy.
- Config productivo: 7 cards, inputs secretos vacíos, consola limpia.
- Acceso anónimo a integraciones: HTTP 401.
- Football block test: `partial`, 0 inserted, 0 updated, 1 skipped; ninguna petición al proveedor.
- Log sanitizado: `football sync blocked until a tested Config credential is active`.
- Credenciales UI configuradas: 0.
- Credenciales en `docker inspect`, logs y `/api/info`: ninguna.

Backup previo al despliegue: `backups/phase0c_20260711_115601/`.

- SQLite SHA-256: `0b5404c3b07f7622338e8461282176e55919d6b6065256a7f76dd297691cf057`.
- `.env` SHA-256: `f88e6750c95b46c2b55830a4efac33807f817b6b3bbd97bd7c58e8d4d7d1684d`.
- Clave maestra, respaldada por separado tras su primera generación: SHA-256 `3f2ab9202f70debb2c8fe1fb7a9a590cae3ae96f4cfc6d62d437d8211831a417`.
- SQLite: `integrity_check=ok`.
- Directorio: `0700`; `.env` y clave maestra: `0600`; SQLite: `0640`.

La aplicación está lista para la acción del usuario. El secreto bootstrap debe leerse localmente, sin copiarlo a chats o reportes, mediante acceso administrativo al contenedor/servidor. Después del login en Config, una clave nueva y distinta debe ingresarse en Football-data.org → Guardar nueva. Hasta entonces football continúa bloqueado.

## Validación del bootstrap y contención

El usuario informó una nueva clave guardada desde Config. La validación posterior detectó, sin imprimir el valor, que el candidato coincidía byte por byte con la credencial heredada del `.env` previo al despliegue. Por lo tanto no se aceptó como rotación segura.

- El primer sync controlado fue el run 11 y terminó `success`, sin errores, antes de detectar la coincidencia.
- El override fue marcado `quarantined` y quedó excluido de `SecretProvider`.
- Se registró auditoría `bootstrap_validation=failed` con código sanitizado `matches_legacy_env`.
- La variable fue retirada del `.env`; hash posterior: `58da4a8f57993f32879573cbc1ab0a8c5f11ee888cb47e5ab31afcecadeb4123`.
- App y worker fueron recreados una vez para soltar el inode antiguo del bind mount de `.env`.
- El archivo montado ya no contiene la variable ni el valor legado.
- Fuente efectiva de football: `unconfigured`.
- App, worker y browser: `healthy`.
- SQLite: `integrity_check=ok`.
- Escaneo en SQLite, logs, HTML y `/api/info`: sin credencial en texto plano.
- Logs: cero coincidencias de headers `Authorization`, `X-Auth-Token` o asignaciones de la variable.

Para cerrar 0C, la credencial anterior debe revocarse y debe generarse una credencial realmente distinta. Al guardarla desde Config, la prueba atómica reemplazará el registro en cuarentena; después se repetirá la validación de no coincidencia y un único sync controlado.
