# Seguridad y secretos

## Secretos

- **No commitees `.env`.** Está en `.gitignore` junto a `data/`, `logs/`, `backups/` y `*.db`.
- **No expongas API keys.** `FOOTBALL_DATA_API_KEY` y demás claves viven solo en tu `.env` local; nunca en el código, README, tests ni `.env.example`.
- Si una clave se filtró en un commit, revócala y genera una nueva.

## Alcance de la herramienta

- Pirapire es **analítico**: calcula probabilidades, cuotas justas, valor esperado y recomendaciones.
- **No automatiza apuestas reales.** No coloca apuestas ni interactúa con un cupón/betslip.
- **No inicia sesión** en casas de apuestas ni usa credenciales de usuario.
- **No hace scraping** ni evade captcha, rate limit o mecanismos anti-bot.

## Aposta.LA Browser Worker (opcional, no activo)

- El contenedor principal **no** incluye Playwright ni Chromium.
- El botón "Sincronizar Aposta.LA" registra `manual_required` mientras no exista un worker de navegador externo.
- Un worker opcional (fase posterior) sería un servicio separado, activado a demanda; no forma parte del despliegue por defecto.

## Recomendaciones de red

- Usa Pirapire solo en **LAN o VPN**. No lo expongas directamente a Internet sin un reverse proxy con TLS y control de acceso.
- Si lo publicas, ponlo detrás de un proxy (ver `DEPLOYMENT.md`) y restringe el acceso.

## Backups

- El estado está en `data/pirapire.db` (SQLite). Respáldalo periódicamente (ver `DEPLOYMENT.md`).
- Guarda los backups fuera del control de versiones (`backups/` ya está ignorado).
