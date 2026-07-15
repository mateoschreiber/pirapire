(function () {
  "use strict";
  const API = "/api/lol/matches";

  function el(id) { return document.getElementById(id); }
  function qs(sel, ctx) { return (ctx || document).querySelector(sel); }
  function qsa(sel, ctx) { return (ctx || document).querySelectorAll(sel); }

  function hide(el) { if (el) el.classList.add("hidden"); }
  function show(el) { if (el) el.classList.remove("hidden"); }

  function fmtTime(iso) {
    if (!iso) return "N/D";
    const d = new Date(iso);
    return d.toLocaleTimeString("es-PY", { hour: "2-digit", minute: "2-digit" });
  }

  function fmtDate(iso) {
    if (!iso) return "N/D";
    return new Date(iso).toLocaleDateString("es-PY", { day: "2-digit", month: "2-digit" });
  }

  function fmtSeconds(s) {
    if (s == null) return "N/D";
    const m = Math.floor(s / 60);
    const sec = s % 60;
    if (m >= 60) { const h = Math.floor(m / 60); return h + "h " + (m % 60) + "m"; }
    return m + "m " + sec + "s";
  }

  function fmtPct(v) {
    if (v == null) return "N/D";
    return v.toFixed(1) + "%";
  }

  function fmtOdds(v) {
    if (v == null) return '<span class="odds-nd">N/D</span>';
    return '<span class="odds-value">' + v.toFixed(2) + "</span>";
  }

  async function fetchJSON(url, opts) {
    const ctrl = new AbortController();
    const timer = setTimeout(function () { return ctrl.abort(); }, 15000);
    try {
      var res = await fetch(url, Object.assign({ signal: ctrl.signal }, opts || {}));
      clearTimeout(timer);
      if (!res.ok) { throw new Error("HTTP " + res.status); }
      return await res.json();
    } catch (e) {
      clearTimeout(timer);
      throw e;
    }
  }

  // --- Dashboard ---
  async function initDashboard() {
    var container = el("matches-container");
    var emptyEl = el("empty-state");
    var errorEl = el("error-state");
    if (!container) return;
    try {
      var data = await fetchJSON(API + "/upcoming?hours=48");
      if (!data.matches || data.matches.length === 0) {
        hide(container);
        show(emptyEl);
        hide(errorEl);
        return;
      }
      hide(emptyEl);
      hide(errorEl);
      show(container);
      renderMatches(container, data.matches);
      el("last-update") && (el("last-update").textContent = new Date().toLocaleTimeString("es-PY"));
    } catch (e) {
      hide(container);
      hide(emptyEl);
      show(errorEl);
      console.error("Dashboard load failed:", e);
    }
  }

  function renderMatches(container, matches) {
    container.innerHTML = "";
    var tbl = document.createElement("table");
    tbl.innerHTML = "<thead><tr><th>Liga</th><th>Equipo A</th><th>Equipo B</th><th>Fecha</th><th>Hora</th><th>Odd A</th><th>Odd B</th><th>Odds</th></tr></thead>";
    var tbody = document.createElement("tbody");
    matches.forEach(function (m) {
      var tr = document.createElement("tr");
      tr.setAttribute("tabindex", "0");
      tr.setAttribute("role", "link");
      tr.addEventListener("click", function () { window.location.href = "/lol/matches/" + m.match_key; });
      tr.addEventListener("keydown", function (e) { if (e.key === "Enter") { window.location.href = "/lol/matches/" + m.match_key; } });
      var oddStatus = m.odds_provider ? '<span class="badge badge-green">' + m.odds_provider + "</span>" : '<span class="badge badge-gray">N/D</span>';
      tr.innerHTML = "<td>" + (m.league || m.tournament || "N/D") + "</td><td class='team-name'>" + m.team_a + "</td><td class='team-name'>" + m.team_b + "</td><td>" + fmtDate(m.start_time_utc) + "</td><td>" + fmtTime(m.start_time_utc) + "</td><td>" + fmtOdds(m.odds_a) + "</td><td>" + fmtOdds(m.odds_b) + "</td><td>" + oddStatus + "</td>";
      tbody.appendChild(tr);
    });
    tbl.appendChild(tbody);
    container.appendChild(tbl);
  }

  // --- Match Detail ---
  async function initMatchDetail() {
    if (typeof MATCH_KEY === "undefined") return;
    try {
      var match = await fetchJSON(API + "/" + MATCH_KEY);
      renderMatchHeader(match);
      renderMatchOdds(match);
      await loadStatistics();
    } catch (e) {
      el("match-title") && (el("match-title").textContent = "Error al cargar el encuentro");
      console.error("Match detail load failed:", e);
    }
  }

  function renderMatchHeader(m) {
    el("match-title") && (el("match-title").textContent = m.team_a + " vs " + m.team_b);
    var hdr = el("match-header");
    if (!hdr) return;
    hdr.innerHTML += "<p>" + (m.league || "") + (m.tournament ? " - " + m.tournament : "") + "</p><p>" + fmtTime(m.start_time_utc) + " (America/Asuncion)" + (m.best_of ? " | BO" + m.best_of : "") + " | " + m.status + "</p>";
  }

  function renderMatchOdds(m) {
    var c = el("odds-content");
    if (!c) return;
    c.innerHTML = "<p><strong>" + m.team_a + ":</strong> " + fmtOdds(m.odds_a) + " | <strong>" + m.team_b + ":</strong> " + fmtOdds(m.odds_b) + "</p>" + (m.odds_provider ? "<p class='meta'>Proveedor: " + m.odds_provider + " | " + (m.odds_captured_at ? fmtTime(m.odds_captured_at) : "") + "</p>" : "");
  }

  async function loadStatistics() {
    try {
      var stats = await fetchJSON(API + "/" + MATCH_KEY + "/statistics");
      renderStats(stats);
    } catch (e) {
      var s = el("stats-section");
      if (s) s.innerHTML += "<p class='error-state'>Estadisticas no disponibles aun.</p>";
      console.error("Stats load failed:", e);
    }
  }

  function renderStats(stats) {
    if (!stats || !stats.payload) return;
    var p = stats.payload;
    var cov = stats.coverage || {};

    renderTeamStats("team-a-stats", p.team_a, cov.team_a);
    renderTeamStats("team-b-stats", p.team_b, cov.team_b);
    renderPlayers("players-section", p);
  }

  function renderTeamStats(elId, data, coverage) {
    var c = el(elId);
    if (!c || !data) return;
    var covClass = coverage === "complete" ? "badge-green" : coverage === "partial" ? "badge-yellow" : "badge-red";
    var covLabel = coverage === "complete" ? "Completa" : coverage === "partial" ? "Parcial" : "No disponible";
    c.innerHTML = "<h4>" + data.team_name + ' <span class="badge ' + covClass + '">' + covLabel + "</span></h4>" +
      "<table class='stats-table'><tr><th>Metrica</th><th>Valor</th></tr>" +
      "<tr><td>Torretas %</td><td>" + fmtPct(data.towers_pct) + "</td></tr>" +
      "<tr><td>Inhibidores %</td><td>" + fmtPct(data.inhibitors_pct) + "</td></tr>" +
      "<tr><td>Asesinatos %</td><td>" + fmtPct(data.kills_pct) + "</td></tr>" +
      "<tr><td>Muertes %</td><td>" + fmtPct(data.deaths_pct) + "</td></tr>" +
      "<tr><td>Dragones %</td><td>" + fmtPct(data.dragons_pct) + "</td></tr>" +
      "<tr><td>Barones %</td><td>" + fmtPct(data.barons_pct) + "</td></tr>" +
      "<tr><td>Oro final %</td><td>" + fmtPct(data.final_gold_pct) + "</td></tr>" +
      "<tr><td>Dur. media mapa</td><td>" + fmtSeconds(data.avg_map_duration_seconds) + "</td></tr>" +
      "<tr><td>Dur. media serie</td><td>" + fmtSeconds(data.avg_series_duration_seconds) + "</td></tr>" +
      "</table>";
  }

  function renderPlayers(elId, payload) {
    var c = el(elId);
    if (!c) return;
    var html = "";
    if (payload.players_a) { html += renderPlayerTable(payload.team_a_name || "Equipo A", payload.players_a); }
    if (payload.players_b) { html += renderPlayerTable(payload.team_b_name || "Equipo B", payload.players_b); }
    c.innerHTML = html;
  }

  function renderPlayerTable(teamName, players) {
    var h = "<h4>" + teamName + "</h4><table><thead><tr><th>Jugador</th><th>Rol</th><th>Mapas</th><th>Kills%</th><th>Deaths%</th><th>Oro%</th><th>Solo Kills%</th><th>CS%</th></tr></thead><tbody>";
    players.forEach(function (p) {
      h += "<tr><td>" + p.player_name + "</td><td>" + (p.role || "N/D") + "</td><td>" + (p.maps_played || 0) + "</td>" +
        "<td>" + fmtPct(p.kills_pct) + "</td><td>" + fmtPct(p.deaths_pct) + "</td>" +
        "<td>" + fmtPct(p.final_gold_pct) + "</td><td>" + fmtPct(p.solo_kills_pct) + "</td>" +
        "<td>" + fmtPct(p.cs_pct) + "</td></tr>";
    });
    h += "</tbody></table>";
    return h;
  }

  function refreshData() { initDashboard(); }

  // Auto-init
  var page = document.body.getAttribute("data-page");
  if (page === "dashboard") { initDashboard(); }
  else if (page === "match-detail") { initMatchDetail(); }

  window.refreshData = refreshData;
  window.initDashboard = initDashboard;
  window.initMatchDetail = initMatchDetail;
})();
