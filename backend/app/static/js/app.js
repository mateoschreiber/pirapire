(function () {
  "use strict";
  const API = "/api/lol/matches";
  const DISPLAY_TIMEZONE = "America/Asuncion";
  let dashboardData = null;
  let activeCompetition = "ALL";
  let matchDetailData = null;

  function el(id) { return document.getElementById(id); }
  function hide(node) { if (node) node.classList.add("hidden"); }
  function show(node) { if (node) node.classList.remove("hidden"); }
  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return {"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;"}[char];
    });
  }

  function fmtTime(iso) {
    if (!iso) return "N/D";
    return new Date(iso).toLocaleTimeString("es-PY", {
      timeZone: DISPLAY_TIMEZONE, hour: "2-digit", minute: "2-digit", hour12: false
    });
  }

  function fmtDate(iso) {
    if (!iso) return "N/D";
    return new Date(iso).toLocaleDateString("es-PY", {
      timeZone: DISPLAY_TIMEZONE, day: "2-digit", month: "2-digit", year: "numeric"
    });
  }

  function fmtSeconds(seconds) {
    if (seconds == null) return "N/D";
    var minutes = Math.floor(seconds / 60);
    var remaining = Math.round(seconds % 60);
    if (minutes >= 60) return Math.floor(minutes / 60) + "h " + (minutes % 60) + "m";
    return minutes + "m " + remaining + "s";
  }

  function fmtPct(value) { return value == null ? "N/D" : Number(value).toFixed(1) + "%"; }
  function fmtNumber(value) { return value == null ? "N/D" : Number(value).toLocaleString("es-PY"); }
  function fmtOdds(value) { return value == null ? "N/D" : Number(value).toFixed(2); }

  async function fetchJSON(url, options) {
    const controller = new AbortController();
    const timer = setTimeout(function () { controller.abort(); }, 20000);
    try {
      const response = await fetch(url, Object.assign({signal: controller.signal}, options || {}));
      clearTimeout(timer);
      if (!response.ok) throw new Error("HTTP " + response.status);
      return await response.json();
    } catch (error) {
      clearTimeout(timer);
      throw error;
    }
  }

  function initLiveClock() {
    const node = el("live-clock");
    if (!node || node.dataset.running === "true") return;
    node.dataset.running = "true";
    const format = new Intl.DateTimeFormat("es-PY", {
      timeZone: DISPLAY_TIMEZONE,
      hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false
    });
    function tick() { node.textContent = format.format(new Date()); }
    tick();
    window.setInterval(tick, 1000);
  }

  // Dashboard
  async function initDashboard() {
    const container = el("matches-container");
    if (!container) return;
    container.innerHTML = '<div class="skeleton dashboard-skeleton"></div>';
    hide(el("empty-state"));
    hide(el("error-state"));
    try {
      dashboardData = await fetchJSON(API + "/upcoming?hours=336");
      renderDashboard();
    } catch (error) {
      hide(container);
      hide(el("empty-state"));
      show(el("error-state"));
      console.error("Dashboard load failed:", error);
    }
  }

  function selectCompetition(code) {
    activeCompetition = code;
    renderDashboard();
  }

  function renderDashboard() {
    if (!dashboardData) return;
    renderCompetitionFilters(dashboardData.competitions || []);
    renderCompetitionCards(dashboardData.competitions || []);
    renderMatches(el("matches-container"), dashboardData.matches || []);
  }

  function renderCompetitionFilters(competitions) {
    const container = el("competition-filter");
    if (!container) return;
    const items = [{code: "ALL", label: "Todos", upcoming_matches: dashboardData.count || 0}].concat(competitions);
    container.innerHTML = items.map(function (item) {
      const active = item.code === activeCompetition ? " active" : "";
      return '<button type="button" class="competition-pill' + active + '" data-code="' + esc(item.code) + '">' +
        esc(item.label) + '<span>' + Number(item.upcoming_matches || 0) + "</span></button>";
    }).join("");
    container.querySelectorAll("button").forEach(function (button) {
      button.addEventListener("click", function () { selectCompetition(button.dataset.code); });
    });
  }

  function renderCompetitionCards(competitions) {
    const container = el("competitions-container");
    if (!container) return;
    const visible = activeCompetition === "ALL" ? competitions : competitions.filter(function (item) { return item.code === activeCompetition; });
    container.innerHTML = visible.map(function (item) {
      const teams = item.qualified_teams || [];
      const teamHtml = teams.length
        ? '<div class="team-chip-list">' + teams.map(function (team) { return '<span class="team-chip">' + esc(team) + "</span>"; }).join("") + "</div>"
        : '<p class="competition-empty">Clasificación todavía no publicada en el calendario.</p>';
      return '<article class="competition-card" data-code="' + esc(item.code) + '">' +
        '<div class="competition-card-head"><div><span class="competition-code">' + esc(item.label) + "</span>" +
        '<p>Temporada ' + esc(item.season) + "</p></div>" +
        '<span class="badge badge-gray">' + item.team_count + " equipos</span></div>" + teamHtml + "</article>";
    }).join("");
    const available = competitions.filter(function (item) { return item.team_count > 0; }).length;
    if (el("competition-coverage")) el("competition-coverage").textContent = available + " de 9 torneos con equipos publicados";
  }

  function oddsHtml(match) {
    if (match.odds_available) {
      return '<div class="match-odds available"><span>' + esc(match.team_a) + " <strong>" + fmtOdds(match.odds_a) + "</strong></span>" +
        '<span>' + esc(match.team_b) + " <strong>" + fmtOdds(match.odds_b) + "</strong></span>" +
        '<small>' + esc(match.odds_provider || "Proveedor externo") + (match.odds_captured_at ? " · " + esc(fmtTime(match.odds_captured_at)) : "") + "</small></div>";
    }
    return '<div class="match-odds unavailable"><strong>Sin cuotas capturadas</strong><small>Oracle’s Elixir no contiene odds.</small></div>';
  }

  function renderMatches(container, matches) {
    if (!container) return;
    const visible = activeCompetition === "ALL" ? matches : matches.filter(function (match) { return match.competition_code === activeCompetition; });
    if (el("matches-count")) el("matches-count").textContent = visible.length + (visible.length === 1 ? " partido" : " partidos");
    if (!visible.length) {
      hide(container);
      show(el("empty-state"));
      return;
    }
    hide(el("empty-state"));
    show(container);
    container.innerHTML = visible.map(function (match) {
      return '<article class="match-card" tabindex="0" role="link" data-key="' + esc(match.match_key) + '">' +
        '<div class="match-card-top"><span class="competition-code">' + esc(match.competition) + "</span>" +
        '<span class="match-datetime">' + esc(fmtDate(match.start_time_utc)) + " · " + esc(fmtTime(match.start_time_utc)) + "</span></div>" +
        '<div class="match-versus"><strong>' + esc(match.team_a) + '</strong><span>VS</span><strong>' + esc(match.team_b) + "</strong></div>" +
        '<div class="match-meta"><span>' + (match.best_of ? "BO" + match.best_of : "Formato N/D") + "</span><span>Programado</span><span>Hora PY</span></div>" +
        oddsHtml(match) + "</article>";
    }).join("");
    container.querySelectorAll(".match-card").forEach(function (card) {
      function open() { window.location.href = "/lol/matches/" + encodeURIComponent(card.dataset.key); }
      card.addEventListener("click", open);
      card.addEventListener("keydown", function (event) { if (event.key === "Enter" || event.key === " ") open(); });
    });
  }

  // Match detail
  async function initMatchDetail() {
    if (typeof MATCH_KEY === "undefined") return;
    try {
      const match = await fetchJSON(API + "/" + encodeURIComponent(MATCH_KEY));
      matchDetailData = match;
      renderMatchHeader(match);
      renderMatchOdds(match);
      await loadStatistics();
    } catch (error) {
      if (el("match-title")) el("match-title").textContent = "Error al cargar el encuentro";
      console.error("Match detail load failed:", error);
    }
  }

  function renderMatchHeader(match) {
    if (el("match-title")) el("match-title").textContent = match.team_a + " vs " + match.team_b;
    const header = el("match-header");
    if (!header) return;
    let meta = header.querySelector(".match-detail-meta");
    if (!meta) { meta = document.createElement("div"); meta.className = "match-detail-meta"; header.appendChild(meta); }
    meta.innerHTML = '<span class="competition-code">' + esc(match.competition || match.league || "N/D") + "</span>" +
      '<span>' + esc(fmtDate(match.start_time_utc)) + " · " + esc(fmtTime(match.start_time_utc)) + " PY</span>" +
      '<span>' + (match.best_of ? "BO" + match.best_of : "Formato N/D") + "</span>";
  }

  function renderMatchOdds(match, estimated) {
    const container = el("odds-content");
    const badge = el("market-source-badge");
    if (!container) return;
    if (estimated && estimated.available) {
      const sideA = estimated.team_a;
      const sideB = estimated.team_b;
      if (badge) { badge.textContent = "Modelo estadístico"; badge.className = "badge badge-blue"; }
      let external = "";
      if (match && match.odds_available) {
        external = '<div class="external-odds"><strong>Referencia externa</strong><span>' + esc(match.team_a) + " " + fmtOdds(match.odds_a) +
          " · " + esc(match.team_b) + " " + fmtOdds(match.odds_b) + "</span><small>" + esc(match.odds_provider || "Proveedor externo") + "</small></div>";
      }
      container.innerHTML = '<div class="market-model"><div class="odds-grid estimated">' +
        '<div><span>' + esc(sideA.name) + '<small>' + fmtPct(sideA.probability_pct) + ' probabilidad · ' + sideA.series_wins + '/' + sideA.series_used + ' series</small></span><strong>' + fmtOdds(sideA.decimal_odds) + '</strong></div>' +
        '<div><span>' + esc(sideB.name) + '<small>' + fmtPct(sideB.probability_pct) + ' probabilidad · ' + sideB.series_wins + '/' + sideB.series_used + ' series</small></span><strong>' + fmtOdds(sideB.decimal_odds) + '</strong></div>' +
        '</div><p class="meta"><strong>Cuotas justas estimadas.</strong> ' + esc(estimated.model) + ' · ' + esc(estimated.method) + '.</p>' + external + '</div>';
      return;
    }
    if (match && match.odds_available) {
      if (badge) { badge.textContent = "Fuente externa"; badge.className = "badge badge-gray"; }
      container.innerHTML = '<div class="odds-grid"><div><span>' + esc(match.team_a) + '</span><strong>' + fmtOdds(match.odds_a) +
        '</strong></div><div><span>' + esc(match.team_b) + '</span><strong>' + fmtOdds(match.odds_b) + "</strong></div></div>" +
        '<p class="meta">Proveedor: ' + esc(match.odds_provider) + (match.odds_captured_at ? " · Captura " + esc(fmtTime(match.odds_captured_at)) : "") + "</p>";
      return;
    }
    if (!estimated) {
      if (badge) { badge.textContent = "Calculando"; badge.className = "badge badge-gray"; }
      container.innerHTML = '<div class="market-loading"><span class="skeleton"></span><p>Calculando cuotas con la forma reciente de ambos equipos…</p></div>';
      return;
    }
    if (badge) { badge.textContent = "Datos insuficientes"; badge.className = "badge badge-yellow"; }
    container.innerHTML = '<div class="source-warning"><strong>No se pudieron estimar las cuotas.</strong><p>' + esc(estimated.reason || "No hay historial suficiente para ambos equipos.") + "</p></div>";
  }

  async function loadStatistics() {
    try {
      const stats = await fetchJSON(API + "/" + encodeURIComponent(MATCH_KEY) + "/statistics");
      renderStats(stats);
    } catch (error) {
      const section = el("stats-section");
      if (section) section.insertAdjacentHTML("beforeend", '<p class="error-state">Estadísticas no disponibles todavía.</p>');
      console.error("Stats load failed:", error);
    }
  }

  function renderStats(stats) {
    if (!stats || !stats.payload) return;
    const payload = stats.payload;
    const coverage = stats.coverage || {};
    renderMatchOdds(matchDetailData, payload.estimated_market);
    renderTeamStats("team-a-stats", payload.team_a, coverage.team_a);
    renderTeamStats("team-b-stats", payload.team_b, coverage.team_b);
    renderPlayers("players-section", payload);
    if (el("coverage-info")) {
      const notes = payload.data_notes || {};
      el("coverage-info").innerHTML = '<strong>Cobertura de datos</strong><ul>' + Object.keys(notes).map(function (key) {
        return "<li>" + esc(notes[key]) + "</li>";
      }).join("") + "</ul>";
    }
  }

  function averageValue(metric, decimals) {
    if (!metric || metric.value == null) return "N/D";
    return Number(metric.value).toLocaleString("es-PY", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  function renderTeamStats(elementId, data, coverage) {
    const container = el(elementId);
    if (!container || !data) return;
    const className = coverage === "complete" ? "badge-green" : coverage === "partial" ? "badge-yellow" : "badge-red";
    const label = coverage === "complete" ? "Completa" : coverage === "partial" ? "Parcial" : "No disponible";
    const averages = data.averages || {};
    container.innerHTML = '<div class="stats-team-head"><div><h4>' + esc(data.team_name) + '</h4><p>' + data.series_used + " series · " + data.maps_used +
      ' mapas</p></div><span class="badge ' + className + '">' + label + "</span></div>" +
      "<div class='table-scroll'><table class='stats-table'><thead><tr><th>Indicador</th><th>Valor · últimas 5 series</th></tr></thead><tbody>" +
      "<tr class='highlight-row'><td>Porcentaje de victorias</td><td><strong>" + fmtPct(data.win_rate_pct) + "</strong><small>" + data.series_wins + " victorias · " + data.series_losses + " derrotas</small></td></tr>" +
      "<tr><td>Torretas destruidas · promedio por mapa</td><td>" + averageValue(averages.towers, 2) + "</td></tr>" +
      "<tr><td>Inhibidores destruidos · promedio por mapa</td><td>" + averageValue(averages.inhibitors, 2) + "</td></tr>" +
      "<tr><td>Asesinatos · promedio por mapa</td><td>" + averageValue(averages.kills, 2) + "</td></tr>" +
      "<tr><td>Muertes · promedio por mapa</td><td>" + averageValue(averages.deaths, 2) + "</td></tr>" +
      "<tr><td>Dragones asesinados · promedio por mapa</td><td>" + averageValue(averages.dragons, 2) + "</td></tr>" +
      "<tr><td>Barones asesinados · promedio por mapa</td><td>" + averageValue(averages.barons, 2) + "</td></tr>" +
      "<tr><td>Oro total · promedio por mapa</td><td>" + averageValue(averages.gold, 0) + "</td></tr>" +
      "<tr><td>Duración promedio del mapa</td><td>" + fmtSeconds(data.avg_map_duration_seconds && data.avg_map_duration_seconds.value) + "</td></tr>" +
      "<tr><td>Duración promedio de la serie</td><td>" + fmtSeconds(data.avg_series_duration_seconds && data.avg_series_duration_seconds.value) + "</td></tr>" +
      "</tbody></table></div>";
  }

  function renderPlayers(elementId, payload) {
    const container = el(elementId);
    if (!container) return;
    let html = '<div class="section-heading player-heading"><div><p class="eyebrow">Detalle individual</p><h3>Jugadores</h3></div></div>';
    html += renderPlayerTable(payload.team_a_name || "Equipo A", payload.players_a || []);
    html += renderPlayerTable(payload.team_b_name || "Equipo B", payload.players_b || []);
    container.innerHTML = html;
  }

  function valueAndShare(value, share) {
    if (value == null) return "N/D";
    return '<strong>' + fmtNumber(value) + "</strong><small>" + fmtPct(share) + " del equipo</small>";
  }

  function renderPlayerTable(teamName, players) {
    let html = '<div class="player-table-block"><h4>' + esc(teamName) + '</h4><div class="table-scroll"><table><thead><tr>' +
      "<th>Jugador</th><th>Rol</th><th>Mapas jugados</th><th>Asesinatos</th><th>Muertes</th><th>Oro promedio por mapa</th><th>CS promedio por mapa</th></tr></thead><tbody>";
    players.forEach(function (player) {
      const cs = player.cs_per_map == null ? '<span class="metric-unavailable">N/D</span>' : Number(player.cs_per_map).toFixed(1);
      const gold = player.gold_per_map == null ? '<span class="metric-unavailable">N/D</span>' : fmtNumber(Math.round(player.gold_per_map));
      html += "<tr><td><strong>" + esc(player.player_name) + "</strong></td><td>" + esc(player.role || "N/D") + "</td><td>" +
        fmtNumber(player.maps_played) + "</td><td>" + fmtNumber(player.kills) + "</td><td>" + fmtNumber(player.deaths) +
        "</td><td>" + gold + "</td><td>" + cs + "</td></tr>";
    });
    if (!players.length) html += '<tr><td colspan="7" class="metric-unavailable">Sin historial estadístico para este equipo.</td></tr>';
    return html + "</tbody></table></div></div>";
  }

  function refreshData() { initDashboard(); }

  initLiveClock();
  const page = document.body.getAttribute("data-page");
  if (page === "dashboard") initDashboard();
  else if (page === "match-detail") initMatchDetail();

  window.refreshData = refreshData;
  window.initDashboard = initDashboard;
  window.initMatchDetail = initMatchDetail;
})();
