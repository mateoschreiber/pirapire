# Fase 4B0 — reparación de verificación API-Football

## Causa raíz

El proveedor estaba presente en el catálogo de Config, pero `test_candidate` no tenía rama `api_football`; por eso Probar y Guardar devolvían `provider_not_testable` sin realizar una prueba válida.

## Contrato efectivo

- URL: `https://v3.football.api-sports.io/status` (sin query ni secreto).
- Método: GET, con timeout explícito del cliente compartido y TLS verificado por defecto.
- Header: `x-apisports-key` exclusivamente.
- Criterio: HTTP 200, content type JSON, objeto JSON y `errors` vacío. No se exige lista de fixtures/countries.
- La clave se aplica con `strip()` sólo al inicio/final, se prueba antes de cifrar y sólo se persiste cifrada tras éxito.

## Diagnóstico saneado

Las rutas devuelven únicamente categorías: `invalid_key`, `forbidden`, `quota_exceeded`, `timeout`, `invalid_response` o `provider_unavailable`. Auditoría guarda categoría, nunca header, clave, token cifrado ni payload. No hubo una prueba real en esta fase porque la clave permanece bajo control del usuario.

## Verificación

Mocks validaron 200 JSON, 401, 403, 429, timeout y JSON inválido; además verificaron que no se usa `X-Auth-Token` ni `x-rapidapi-key`. El siguiente paso del usuario es ingresar su misma clave y pulsar **Probar**; sólo un éxito permitirá **Guardar nueva**, que devolverá `source=ui` sin revelar el valor.
