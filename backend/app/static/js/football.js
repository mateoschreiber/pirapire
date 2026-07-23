(function () {
  "use strict";

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"}[char];
    });
  }

  function formatStart(value) {
    return new Date(value).toLocaleString("es-PY", {
      timeZone: "America/Asuncion", dateStyle: "short", timeStyle: "short"
    });
  }

  async function initFootballDashboard() {
    const container = document.getElementById("football-matches-container");
    const count = document.getElementById("football-matches-count");
    if (!container || !count) return;
    try {
      const response = await fetch("/api/football/matches/upcoming?hours=336");
      if (!response.ok) throw new Error("No se pudo cargar la agenda de fútbol.");
      const data = await response.json();
      count.textContent = data.count + (data.count === 1 ? " partido" : " partidos");
      if (!data.matches.length) {
        const message = data.source_status === 'not_configured'
          ? 'Configure una API en <a href="/sources">Fuentes</a> y pulse “Sincronizar datos”.'
          : data.source_status === 'degraded'
            ? 'La última sincronización falló: ' + esc(data.source_message || 'revise la clave y la configuración de la API en Fuentes.')
            : 'La API no devolvió próximos partidos. Puede volver a sincronizar cuando haya fixtures disponibles.';
        container.innerHTML = '<div class="empty-state football-empty"><p>No hay partidos locales todavía. ' + message + '</p></div>';
        return;
      }
      container.innerHTML = data.matches.map(function (match) {
        return '<article class="match-card"><div class="match-card-top"><span class="competition-code">' +
          esc(match.competition || "Competición") + '</span><span class="match-datetime">' +
          esc(formatStart(match.start_time_utc)) + '</span></div><div class="match-versus"><strong>' +
          esc(match.home_team) + '</strong><span>VS</span><strong>' + esc(match.away_team) +
          "</strong></div></article>";
      }).join("");
    } catch (error) {
      count.textContent = "Error";
      container.innerHTML = '<div class="error-state"><p>' + esc(error.message) + "</p></div>";
    }
  }

  async function monitorSync(runId, button, status) {
    while (true) {
      const response = await fetch('/api/sources/runs/' + encodeURIComponent(runId));
      if (!response.ok) throw new Error('No se pudo consultar el estado de la sincronización.');
      const run = await response.json();
      if (run.status === 'queued' || run.status === 'running') {
        status.textContent = 'Sincronizando fixtures…';
        await new Promise(function (resolve) { setTimeout(resolve, 1500); });
        continue;
      }
      if (run.status !== 'success') throw new Error(run.error_message || 'La sincronización no pudo completarse.');
      status.textContent = 'Sincronización completada: ' + (run.records_received || 0) + ' fixtures recibidos.';
      button.disabled = false;
      await initFootballDashboard();
      return;
    }
  }

  function initFootballSync() {
    const button = document.getElementById('football-sync-button');
    const token = document.getElementById('football-admin-token');
    const status = document.getElementById('football-sync-status');
    if (!button || !token || !status) return;
    button.addEventListener('click', async function () {
      if (!token.value) { status.textContent = 'Ingrese el token administrativo para sincronizar.'; return; }
      button.disabled = true;
      status.textContent = 'Iniciando sincronización…';
      try {
        const response = await fetch('/api/football/sync', {method: 'POST', headers: {'X-Admin-Token': token.value}});
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'No se pudo iniciar la sincronización.');
        if (result.already_running) status.textContent = 'Ya existe una sincronización en curso.';
        await monitorSync(result.run_id, button, status);
      } catch (error) {
        status.textContent = 'No se pudo sincronizar: ' + error.message;
        button.disabled = false;
      }
    });
  }

  if (document.body.getAttribute("data-page") === "football-dashboard") {
    initFootballDashboard();
    initFootballSync();
  }
})();
