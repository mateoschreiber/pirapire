var Pirapire = (function () {
  "use strict";

  var THEME_KEY = "pirapire.theme";

  function showMessage(text, kind) {
    var el = document.getElementById("flash");
    if (!el) return;
    el.textContent = text;
    el.className = "flash flash-" + (kind || "ok");
    el.removeAttribute("hidden");
    setTimeout(function () {
      el.setAttribute("hidden", "");
      el.textContent = "";
    }, 4500);
  }

  function apiGet(url) {
    return fetch(url).then(function (r) {
      if (!r.ok) throw new Error(r.status + " " + r.statusText);
      return r.json();
    });
  }

  function apiPost(url, body) {
    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then(function (r) {
      if (!r.ok) throw new Error(r.status + " " + r.statusText);
      return r.json();
    });
  }

  function renderTable(id, rows, cols) {
    var tbody = document.querySelector("#" + id + " tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (rows.length === 0) {
      var tr = document.createElement("tr");
      var td = document.createElement("td");
      td.colSpan = cols.length;
      td.textContent = "Sin datos";
      td.className = "muted";
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    rows.forEach(function (row) {
      var tr = document.createElement("tr");
      cols.forEach(function (col) {
        var td = document.createElement("td");
        td.textContent = row[col] !== undefined && row[col] !== null ? row[col] : "";
        tr.appendChild(td);
      });
      tbody.appendChild(tr);
    });
  }

  /* --- Dashboard --- */
  function initDashboard() {
    apiGet("/sports")
      .then(function (d) { document.getElementById("stat-sports").textContent = d.length; })
      .catch(function () { document.getElementById("stat-sports").textContent = "?"; });
    apiGet("/teams")
      .then(function (d) { document.getElementById("stat-teams").textContent = d.length; })
      .catch(function () { document.getElementById("stat-teams").textContent = "?"; });
    apiGet("/matches")
      .then(function (d) { document.getElementById("stat-matches").textContent = d.length; })
      .catch(function () { document.getElementById("stat-matches").textContent = "?"; });
    document.getElementById("stat-predictions").textContent = "n/d";
    apiGet("/health")
      .then(function () {
        var badge = document.getElementById("stat-api");
        badge.textContent = "ok";
        badge.className = "badge badge-ok";
      })
      .catch(function () {
        var badge = document.getElementById("stat-api");
        badge.textContent = "error";
        badge.className = "badge badge-high";
      });
  }

  /* --- Sports --- */
  function initSports() {
    function load() { apiGet("/sports").then(function (r) { renderTable("sports-table", r, ["id", "name", "slug"]); }).catch(function (e) { showMessage("No se pudieron cargar deportes: " + e.message, "error"); }); }
    document.getElementById("sport-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      apiPost("/sports", { name: document.getElementById("sport-name").value, slug: document.getElementById("sport-slug").value })
        .then(function () { showMessage("Deporte creado"); load(); this.reset(); }.bind(this))
        .catch(function (e) { showMessage("Error: " + e.message, "error"); });
    });
    load();
  }

  /* --- Teams --- */
  function initTeams() {
    function load() { apiGet("/teams").then(function (r) { renderTable("teams-table", r, ["id", "sport_id", "name", "short_name"]); }).catch(function (e) { showMessage("No se pudieron cargar equipos: " + e.message, "error"); }); }
    document.getElementById("team-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      apiPost("/teams", {
        sport_id: parseInt(document.getElementById("team-sport-id").value, 10),
        name: document.getElementById("team-name").value,
        short_name: document.getElementById("team-short-name").value || null,
      })
        .then(function () { showMessage("Equipo creado"); load(); this.reset(); }.bind(this))
        .catch(function (e) { showMessage("Error: " + e.message, "error"); });
    });
    load();
  }

  /* --- Matches --- */
  function initMatches() {
    function load() { apiGet("/matches").then(function (r) { renderTable("matches-table", r, ["id", "sport_id", "team_a_id", "team_b_id", "competition", "start_time", "status"]); }).catch(function (e) { showMessage("No se pudieron cargar partidos: " + e.message, "error"); }); }
    document.getElementById("match-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var payload = {
        sport_id: parseInt(document.getElementById("match-sport-id").value, 10),
        team_a_id: parseInt(document.getElementById("match-team-a").value, 10),
        team_b_id: parseInt(document.getElementById("match-team-b").value, 10),
        competition: document.getElementById("match-competition").value || null,
        start_time: document.getElementById("match-start").value || null,
        status: document.getElementById("match-status").value,
      };
      apiPost("/matches", payload)
        .then(function () { showMessage("Partido creado"); load(); this.reset(); }.bind(this))
        .catch(function (e) { showMessage("Error: " + e.message, "error"); });
    });
    load();
  }

  /* --- Odds --- */
  function initOdds() {
    document.getElementById("odds-form").addEventListener("submit", function (ev) {
      ev.preventDefault();
      var payload = { odds_decimal: parseFloat(document.getElementById("odds-decimal").value) };
      var modelProb = document.getElementById("odds-model-prob").value;
      if (modelProb !== "") payload.model_probability = parseFloat(modelProb);
      var stake = document.getElementById("odds-stake").value;
      if (stake !== "") payload.stake = parseFloat(stake);

      apiPost("/odds/analyze", payload).then(function (data) {
        var riskClass = "badge-low";
        if (data.risk_label === "medium") riskClass = "badge-medium";
        else if (data.risk_label === "high") riskClass = "badge-high";
        var html = [
          '<div class="kv"><span>Cuota</span><span>' + data.odds_decimal.toFixed(2) + "</span></div>",
          '<div class="kv"><span>Prob. implícita</span><span>' + (data.implied_probability * 100).toFixed(2) + "%</span></div>",
          '<div class="kv"><span>Prob. modelo</span><span>' + (data.model_probability * 100).toFixed(2) + "%</span></div>",
          '<div class="kv"><span>Cuota justa</span><span>' + data.fair_odds.toFixed(4) + "</span></div>",
          '<div class="kv"><span>Valor esperado</span><span>' + data.expected_value.toFixed(4) + "</span></div>",
          '<div class="kv"><span>Riesgo</span><span><span class="badge ' + riskClass + '">' + data.risk_label + "</span></span></div>",
        ].join("");
        document.getElementById("odds-result").innerHTML = html;
        document.getElementById("odds-result").removeAttribute("hidden");
        document.getElementById("odds-empty").setAttribute("hidden", "");
      }).catch(function (e) {
        showMessage("Error al analizar cuota: " + e.message, "error");
      });
    });
  }

  /* --- Combo --- */
  function initCombo() {
    function collectLegs() {
      var rows = document.querySelectorAll("#legs-container .leg-row");
      var legs = [];
      rows.forEach(function (row) {
        var prob = parseFloat(row.querySelector(".leg-prob").value);
        if (isNaN(prob)) return;
        var leg = { probability: prob };
        var oddsVal = parseFloat(row.querySelector(".leg-odds").value);
        if (!isNaN(oddsVal)) leg.odds_decimal = oddsVal;
        legs.push(leg);
      });
      return legs;
    }

    function bindRemove(btn) {
      btn.addEventListener("click", function () {
        var container = document.getElementById("legs-container");
        if (container.querySelectorAll(".leg-row").length <= 1) return;
        this.closest(".leg-row").remove();
      });
    }

    function addLeg() {
      var template = document.querySelector("#legs-container .leg-row");
      var clone = template.cloneNode(true);
      clone.querySelector(".leg-prob").value = "";
      clone.querySelector(".leg-odds").value = "";
      bindRemove(clone.querySelector(".leg-remove"));
      document.getElementById("legs-container").appendChild(clone);
    }

    document.getElementById("add-leg").addEventListener("click", addLeg);
    document.querySelectorAll(".leg-remove").forEach(bindRemove);

    document.getElementById("combo-analyze-btn").addEventListener("click", function () {
      var legs = collectLegs();
      if (legs.length === 0) { showMessage("Agrega al menos 1 pata con probabilidad", "error"); return; }
      var payload = { legs: legs };
      var offered = parseFloat(document.getElementById("combo-offered-odds").value);
      if (!isNaN(offered)) payload.offered_odds = offered;

      apiPost("/combo/analyze", payload).then(function (data) {
        var riskClass = "badge-low";
        if (data.risk_label === "medium") riskClass = "badge-medium";
        else if (data.risk_label === "high") riskClass = "badge-high";
        var html = [
          '<div class="kv"><span>Patas</span><span>' + data.legs + "</span></div>",
          '<div class="kv"><span>Prob. combinada</span><span>' + (data.combo_probability * 100).toFixed(4) + "%</span></div>",
          '<div class="kv"><span>Cuota justa</span><span>' + data.combo_fair_odds.toFixed(4) + "</span></div>",
        ];
        if (data.offered_odds !== null) html.push('<div class="kv"><span>Cuota ofrecida</span><span>' + data.offered_odds.toFixed(2) + "</span></div>");
        if (data.expected_value !== null) html.push('<div class="kv"><span>Valor esperado</span><span>' + data.expected_value.toFixed(4) + "</span></div>");
        html.push('<div class="kv"><span>Riesgo</span><span><span class="badge ' + riskClass + '">' + data.risk_label + "</span></span></div>");
        document.getElementById("combo-result").innerHTML = html.join("");
        document.getElementById("combo-result").removeAttribute("hidden");
        document.getElementById("combo-empty").setAttribute("hidden", "");
      }).catch(function (e) {
        showMessage("Error al analizar combinada: " + e.message, "error");
      });
    });
  }

  /* --- Tema claro/oscuro (persistente) --- */
  function currentTheme() {
    return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
  }

  function updateThemeButton(theme) {
    var btn = document.getElementById("themeToggle");
    if (!btn) return;
    var dark = theme === "dark";
    // Icono: sol si estamos en oscuro (para pasar a claro), luna si estamos en claro.
    btn.textContent = dark ? "\u2600" : "\u263D";
    btn.setAttribute("aria-label", dark ? "Cambiar a tema claro" : "Cambiar a tema oscuro");
    btn.setAttribute("title", dark ? "Cambiar a tema claro" : "Cambiar a tema oscuro");
  }

  function applyTheme(theme) {
    var t = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", t);
    updateThemeButton(t);
  }

  function saveTheme(theme) {
    try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* almacenamiento no disponible */ }
  }

  function toggleTheme() {
    var next = currentTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
    saveTheme(next);
  }

  function initTheme() {
    // El tema ya fue aplicado por el script inline del <head>; aquí solo
    // sincronizamos el botón y los listeners.
    applyTheme(currentTheme());
    var btn = document.getElementById("themeToggle");
    if (btn && !btn.dataset.bound) {
      btn.addEventListener("click", toggleTheme);
      btn.dataset.bound = "1";
    }
    // Sincroniza el tema entre pestañas abiertas.
    window.addEventListener("storage", function (ev) {
      if (ev.key === THEME_KEY && (ev.newValue === "light" || ev.newValue === "dark")) {
        applyTheme(ev.newValue);
      }
    });
  }

  document.addEventListener("DOMContentLoaded", initTheme);

  /* --- Manual sync (Fase 2) --- */
  var SYNC_ENDPOINTS = {
    football: "/sources/sync/football",
    lol: "/sources/sync/lol",
    all: "/sources/sync/all",
  };

  function setSyncStatus(text) {
    var box = document.getElementById("sync-status");
    if (!box) return;
    box.textContent = text;
    box.removeAttribute("hidden");
  }

  function syncSource(kind) {
    var url = SYNC_ENDPOINTS[kind];
    if (!url) return;
    var buttons = document.querySelectorAll(".toolbar-actions .btn");
    buttons.forEach(function (b) { b.setAttribute("disabled", "disabled"); });
    setSyncStatus("Ejecutando actualizacion (" + kind + ")...");
    apiPost(url, {})
      .then(function (res) {
        setSyncStatus("Run #" + res.run_id + " iniciado (" + res.status + "). Consultando estado...");
        // Una sola consulta de estado tras un breve margen. Sin polling permanente.
        setTimeout(function () {
          apiGet("/source-runs/" + res.run_id)
            .then(function (run) {
              setSyncStatus(
                "Run #" + run.id + " -> " + run.status +
                " | ins:" + run.inserted_records +
                " upd:" + run.updated_records +
                " skip:" + run.skipped_records +
                " err:" + run.error_count
              );
              showMessage("Actualizacion " + kind + ": " + run.status, run.error_count ? "error" : "ok");
            })
            .catch(function (e) { setSyncStatus("No se pudo leer el estado: " + e.message); });
        }, 3500);
      })
      .catch(function (e) {
        setSyncStatus("Error al iniciar: " + e.message);
        showMessage("Error al iniciar sync: " + e.message, "error");
      })
      .finally(function () {
        buttons.forEach(function (b) { b.removeAttribute("disabled"); });
      });
  }

  function recalcRanking() {
    setSyncStatus("Recalculando ranking local (sin internet)...");
    apiPost("/sources/seed", {})
      .then(function (res) {
        setSyncStatus("Ranking recalculado: " + res.sources_upserted + " fuentes, " + res.capabilities_upserted + " capacidades.");
        showMessage("Ranking local recalculado", "ok");
      })
      .catch(function (e) {
        setSyncStatus("Error: " + e.message);
        showMessage("Error al recalcular: " + e.message, "error");
      });
  }

  /* --- Source runs page --- */
  function fmtDate(v) { return v ? String(v).replace("T", " ").slice(0, 19) : ""; }

  var _allRuns = [];
  var _runFilter = "all";

  function runSourceLabel(run) {
    if (run.source_slug) return run.source_slug;
    if (run.sport === "all") return "sync_all";
    return run.sport;
  }

  function renderRuns() {
    var tbody = document.querySelector("#runs-table tbody");
    if (!tbody) return;
    var runs = _runFilter === "all" ? _allRuns : _allRuns.filter(function (r) { return r.status === _runFilter; });
    tbody.innerHTML = "";
    if (!runs.length) {
      tbody.innerHTML = '<tr><td colspan="10" class="muted">Sin ejecuciones.</td></tr>';
      return;
    }
    runs.forEach(function (run) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td>" + run.id + "</td>" +
        "<td>" + run.sport + "</td>" +
        "<td>" + runSourceLabel(run) + "</td>" +
        '<td><span class="badge ' + statusBadge(run.status) + '">' + run.status + "</span></td>" +
        "<td>" + run.inserted_records + "</td>" +
        "<td>" + run.updated_records + "</td>" +
        "<td>" + run.skipped_records + "</td>" +
        "<td>" + run.error_count + "</td>" +
        "<td>" + fmtDate(run.started_at) + "</td>" +
        "<td>" + fmtDate(run.finished_at) + "</td>";
      tr.style.cursor = "pointer";
      tr.addEventListener("click", function () { loadRunLogs(run.id); });
      tbody.appendChild(tr);
    });
  }

  function loadSourceRuns() {
    var tbody = document.querySelector("#runs-table tbody");
    if (!tbody) return;
    apiGet("/source-runs?limit=50").then(function (runs) {
      _allRuns = runs;  // API returns them ordered by id desc
      renderRuns();
    }).catch(function (e) { showMessage("Error cargando ejecuciones: " + e.message, "error"); });
  }

  function statusBadge(status) {
    if (status === "success") return "badge-low";
    if (status === "partial" || status === "running") return "badge-medium";
    if (status === "error") return "badge-high";
    return "badge-muted";
  }

  function loadRunLogs(runId) {
    var table = document.getElementById("logs-table");
    var tbody = table ? table.querySelector("tbody") : null;
    var hint = document.getElementById("logs-hint");
    if (!tbody) return;
    apiGet("/source-runs/" + runId + "/logs").then(function (logs) {
      table.removeAttribute("hidden");
      if (hint) hint.textContent = "Logs de la ejecucion #" + runId;
      tbody.innerHTML = "";
      if (!logs.length) {
        tbody.innerHTML = '<tr><td colspan="3" class="muted">Sin logs.</td></tr>';
        return;
      }
      logs.forEach(function (log) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          '<td><span class="badge ' + (log.level === "error" ? "badge-high" : (log.level === "warning" ? "badge-medium" : "badge-muted")) + '">' + log.level + "</span></td>" +
          "<td>" + log.message + "</td>" +
          "<td>" + fmtDate(log.created_at) + "</td>";
        tbody.appendChild(tr);
      });
    }).catch(function (e) { showMessage("Error cargando logs: " + e.message, "error"); });
  }

  function initSourceRuns() {
    var filterBox = document.getElementById("run-filters");
    if (filterBox && !filterBox.dataset.bound) {
      filterBox.dataset.bound = "1";
      filterBox.querySelectorAll(".filter-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          filterBox.querySelectorAll(".filter-btn").forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
          _runFilter = btn.getAttribute("data-filter");
          renderRuns();
        });
      });
    }
    loadSourceRuns();
  }

  /* --- Data pages --- */
  function initDataFootball() {
    apiGet("/data/football/competitions").then(function (rows) {
      renderTable("competitions-table", rows, ["id", "code", "name", "country", "source_name"]);
    }).catch(function () {});
    apiGet("/data/football/matches").then(function (rows) {
      var tbody = document.querySelector("#matches-table tbody");
      tbody.innerHTML = "";
      if (!rows.length) { tbody.innerHTML = '<tr><td colspan="9" class="muted">Sin partidos.</td></tr>'; return; }
      rows.forEach(function (m) {
        var score = (m.home_score === null ? "-" : m.home_score) + " : " + (m.away_score === null ? "-" : m.away_score);
        var ht = (m.ht_home_score === null || m.ht_home_score === undefined ? "-" : m.ht_home_score) + " : " + (m.ht_away_score === null || m.ht_away_score === undefined ? "-" : m.ht_away_score);
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + m.id + "</td>" +
          "<td>" + fmtDate(m.start_time) + "</td>" +
          "<td>" + (m.status || "") + "</td>" +
          "<td>" + (m.home_team_id || "") + "</td>" +
          "<td>" + (m.away_team_id || "") + "</td>" +
          "<td>" + score + "</td>" +
          "<td>" + ht + "</td>" +
          "<td>" + (m.source_name || "") + "</td>" +
          "<td>" + (m.fallback_used ? "si" : "no") + "</td>";
        tbody.appendChild(tr);
      });
    }).catch(function () {});
    apiGet("/data/football/standings").then(function (rows) {
      renderTable("standings-table", rows, ["position", "team_id", "played_games", "won", "draw", "lost", "points", "goals_for", "goals_against", "goal_difference"]);
    }).catch(function () {});
    apiGet("/data/football/teams").then(function (rows) {
      renderTable("teams-table", rows, ["id", "name", "short_name", "tla", "source_name"]);
    }).catch(function () {});
  }

  function initDataLol() {
    apiGet("/data/lol/patches").then(function (rows) {
      renderTable("patches-table", rows, ["id", "version", "source_name", "retrieved_at"]);
    }).catch(function () {});
    apiGet("/data/lol/champions").then(function (rows) {
      renderTable("champions-table", rows, ["champion_id", "name", "title", "version", "source_name"]);
    }).catch(function () {});
  }

  return {
    showMessage: showMessage,
    apiGet: apiGet,
    apiPost: apiPost,
    renderTable: renderTable,
    initDashboard: initDashboard,
    initSports: initSports,
    initTeams: initTeams,
    initMatches: initMatches,
    initOdds: initOdds,
    initCombo: initCombo,
    initTheme: initTheme,
    applyTheme: applyTheme,
    toggleTheme: toggleTheme,
    syncSource: syncSource,
    recalcRanking: recalcRanking,
    loadSourceRuns: loadSourceRuns,
    initSourceRuns: initSourceRuns,
    initDataFootball: initDataFootball,
    initDataLol: initDataLol,
  };
})();
