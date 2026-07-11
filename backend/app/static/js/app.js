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

  function initTopClock() {
    var el = document.getElementById("top-clock");
    if (!el || el.dataset.bound) return;
    el.dataset.bound = "1";
    var formatter = null;
    try {
      formatter = new Intl.DateTimeFormat("es-PY", {
        timeZone: "America/Asuncion",
        weekday: "short",
        day: "2-digit",
        month: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    } catch (e) {
      formatter = null;
    }
    function tick() {
      var now = new Date();
      el.textContent = formatter ? formatter.format(now) + " PY" : now.toLocaleString();
      window.setTimeout(tick, 1000);
    }
    tick();
  }

  document.addEventListener("DOMContentLoaded", initTopClock);

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
    /* Dashboard counts are server-rendered via Jinja2 (pages.py _dashboard_counts).
       JS only verifies API health. Do NOT overwrite server counts. */
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
      var saveEl = document.getElementById("odds-save");
      if (saveEl && saveEl.checked) {
        payload.save = true;
        var ml = document.getElementById("odds-match-label");
        var mt = document.getElementById("odds-market-text");
        if (ml && ml.value) payload.match_label = ml.value;
        if (mt && mt.value) payload.market_text = mt.value;
      }

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
      var comboSave = document.getElementById("combo-save");
      if (comboSave && comboSave.checked) {
        payload.save = true;
        var cname = document.getElementById("combo-name");
        if (cname && cname.value) payload.name = cname.value;
      }

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

  /* --- Markets (Fase 3) --- */
  function statusBadgeClass(status) {
    if (status === "supported") return "badge-low";
    if (status === "manual_only" || status === "partial" || status === "estimated_only") return "badge-medium";
    return "badge-high";
  }

  function fillMarketTable(id, markets) {
    var tbody = document.querySelector("#" + id + " tbody");
    if (!tbody) return;
    tbody.innerHTML = "";
    if (!markets.length) { tbody.innerHTML = '<tr><td colspan="5" class="muted">Sin mercados. Ejecuta Re-seed.</td></tr>'; return; }
    markets.forEach(function (m) {
      var tr = document.createElement("tr");
      tr.innerHTML =
        "<td><code>" + m.market_code + "</code></td>" +
        "<td>" + m.display_name + "</td>" +
        "<td>" + (m.category || "") + "</td>" +
        '<td><span class="badge ' + statusBadgeClass(m.source_status) + '">' + m.source_status + "</span></td>" +
        "<td>" + m.risk_level + "</td>";
      tbody.appendChild(tr);
    });
  }

  function initMarkets() {
    apiGet("/markets?sport=football").then(function (rows) { fillMarketTable("markets-football", rows); }).catch(function () {});
    apiGet("/markets?sport=lol").then(function (rows) { fillMarketTable("markets-lol", rows); }).catch(function () {});
    apiGet("/markets/aliases").then(function (rows) {
      renderTable("aliases-table", rows, ["alias_text", "normalized_alias", "language"]);
    }).catch(function () {});
  }

  function reseedMarkets() {
    var box = document.getElementById("markets-status");
    if (box) { box.textContent = "Re-seeding..."; box.removeAttribute("hidden"); }
    apiPost("/markets/seed", {}).then(function (res) {
      if (box) box.textContent = "Mercados: " + res.markets_upserted + " nuevos, aliases: " + res.aliases_upserted + " nuevos.";
      showMessage("Market catalog actualizado", "ok");
      initMarkets();
    }).catch(function (e) { showMessage("Error: " + e.message, "error"); });
  }

  /* --- Imports (Fase 3) --- */
  function uploadCsv(url, fileInputId, resultId) {
    var input = document.getElementById(fileInputId);
    var result = document.getElementById(resultId);
    if (!input || !input.files.length) { showMessage("Selecciona un archivo CSV", "error"); return; }
    var fd = new FormData();
    fd.append("file", input.files[0]);
    if (result) { result.hidden = false; result.innerHTML = '<div class="kv"><span>Estado</span><span>subiendo...</span></div>'; }
    fetch(url, { method: "POST", body: fd })
      .then(function (r) { if (!r.ok) throw new Error(r.status + " " + r.statusText); return r.json(); })
      .then(function (b) {
        if (result) {
          result.innerHTML =
            '<div class="kv"><span>Batch</span><span>#' + b.id + '</span></div>' +
            '<div class="kv"><span>Estado</span><span><span class="badge ' + statusBadge(b.status) + '">' + b.status + '</span></span></div>' +
            '<div class="kv"><span>Total</span><span>' + b.total_rows + '</span></div>' +
            '<div class="kv"><span>Importadas</span><span>' + b.imported_rows + '</span></div>' +
            '<div class="kv"><span>Omitidas</span><span>' + b.skipped_rows + '</span></div>' +
            '<div class="kv"><span>Errores</span><span>' + b.error_rows + '</span></div>' +
            '<div class="kv"><span>Mensaje</span><span>' + (b.message || '') + '</span></div>';
        }
        showMessage("Importación batch #" + b.id + ": " + b.status, b.error_rows ? "error" : "ok");
        loadBatches();
      })
      .catch(function (e) { showMessage("Error importando: " + e.message, "error"); });
  }

  function loadBatches() {
    var tbody = document.querySelector("#batches-table tbody");
    if (!tbody) return;
    apiGet("/imports/batches?limit=30").then(function (rows) {
      tbody.innerHTML = "";
      if (!rows.length) { tbody.innerHTML = '<tr><td colspan="9" class="muted">Sin importaciones.</td></tr>'; return; }
      rows.forEach(function (b) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + b.id + "</td>" +
          "<td>" + b.import_type + "</td>" +
          "<td>" + (b.filename || "") + "</td>" +
          '<td><span class="badge ' + statusBadge(b.status) + '">' + b.status + "</span></td>" +
          "<td>" + b.total_rows + "</td>" +
          "<td>" + b.imported_rows + "</td>" +
          "<td>" + b.skipped_rows + "</td>" +
          "<td>" + b.error_rows + "</td>" +
          "<td>" + (b.message || "") + "</td>";
        tr.style.cursor = "pointer";
        tr.addEventListener("click", function () { loadBatchErrors(b.id); });
        tbody.appendChild(tr);
      });
    }).catch(function () {});
  }

  function loadBatchErrors(batchId) {
    var table = document.getElementById("batch-errors-table");
    var tbody = table ? table.querySelector("tbody") : null;
    var hint = document.getElementById("batch-errors-hint");
    if (!tbody) return;
    apiGet("/imports/batches/" + batchId + "/errors").then(function (rows) {
      table.removeAttribute("hidden");
      if (hint) hint.textContent = "Errores/avisos del batch #" + batchId;
      tbody.innerHTML = "";
      if (!rows.length) { tbody.innerHTML = '<tr><td colspan="3" class="muted">Sin errores.</td></tr>'; return; }
      rows.forEach(function (e) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + e.row_number + "</td>" +
          '<td><span class="badge ' + (e.level === "error" ? "badge-high" : "badge-medium") + '">' + e.level + "</span></td>" +
          "<td>" + e.message + "</td>";
        tbody.appendChild(tr);
      });
    }).catch(function () {});
  }

  function initImports() {
    var aposta = document.getElementById("aposta-form");
    if (aposta) aposta.addEventListener("submit", function (ev) {
      ev.preventDefault();
      uploadCsv("/imports/aposta-odds-csv", "aposta-file", "aposta-result");
    });
    var oracles = document.getElementById("oracles-form");
    if (oracles) oracles.addEventListener("submit", function (ev) {
      ev.preventDefault();
      uploadCsv("/imports/oracles-elixir-csv", "oracles-file", "oracles-result");
    });
    loadBatches();
  }

  /* --- History (Fase 3) --- */
  var _historyTab = "predictions";

  function settlePrediction(id, result) {
    apiPost("/history/predictions/" + id + "/settle", { result: result })
      .then(function () { showMessage("Predicción actualizada: " + result, "ok"); loadHistory(); })
      .catch(function (e) { showMessage("Error: " + e.message, "error"); });
  }

  function settleCombo(id, result) {
    apiPost("/history/combos/" + id + "/settle", { result: result })
      .then(function () { showMessage("Combinada actualizada: " + result, "ok"); loadHistory(); })
      .catch(function (e) { showMessage("Error: " + e.message, "error"); });
  }

  function settleButtons(kind, id) {
    var fn = kind === "combo" ? "settleCombo" : "settlePrediction";
    return ["won", "lost", "void", "pending"].map(function (r) {
      return '<button class="btn btn-outline filter-btn" onclick="Pirapire.' + fn + '(' + id + ',\'' + r + '\')">' + r + "</button>";
    }).join(" ");
  }

  function pct(v) { return (v === null || v === undefined) ? "" : (v * 100).toFixed(1) + "%"; }
  function num(v) { return (v === null || v === undefined) ? "" : Number(v).toFixed(3); }

  function loadPredictions() {
    var tbody = document.querySelector("#predictions-table tbody");
    if (!tbody) return;
    apiGet("/history/predictions").then(function (rows) {
      tbody.innerHTML = "";
      if (!rows.length) { tbody.innerHTML = '<tr><td colspan="15" class="muted">Sin predicciones guardadas.</td></tr>'; return; }
      rows.forEach(function (p) {
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + p.id + "</td>" +
          "<td>" + fmtDate(p.created_at) + "</td>" +
          "<td>" + (p.sport || "") + "</td>" +
          "<td>" + (p.match_label || "") + "</td>" +
          "<td>" + (p.market_code || p.market_text || "") + "</td>" +
          "<td>" + (p.line === null || p.line === undefined ? "" : p.line) + "</td>" +
          "<td>" + (p.selection || "") + "</td>" +
          "<td>" + num(p.odds_decimal) + "</td>" +
          "<td>" + pct(p.implied_probability) + "</td>" +
          "<td>" + pct(p.model_probability) + "</td>" +
          "<td>" + num(p.expected_value) + "</td>" +
          '<td><span class="badge ' + riskBadge(p.risk_label) + '">' + (p.risk_label || "") + "</span></td>" +
          "<td>" + p.status + "</td>" +
          "<td>" + (p.result || "") + "</td>" +
          "<td>" + settleButtons("prediction", p.id) + "</td>";
        tbody.appendChild(tr);
      });
    }).catch(function (e) { showMessage("Error: " + e.message, "error"); });
  }

  function loadCombos() {
    var tbody = document.querySelector("#combos-table tbody");
    if (!tbody) return;
    apiGet("/history/combos").then(function (rows) {
      tbody.innerHTML = "";
      if (!rows.length) { tbody.innerHTML = '<tr><td colspan="12" class="muted">Sin combinadas guardadas.</td></tr>'; return; }
      rows.forEach(function (item) {
        var c = item.combo;
        var tr = document.createElement("tr");
        tr.innerHTML =
          "<td>" + c.id + "</td>" +
          "<td>" + fmtDate(c.created_at) + "</td>" +
          "<td>" + (c.name || "") + "</td>" +
          "<td>" + item.legs.length + "</td>" +
          "<td>" + num(c.offered_odds) + "</td>" +
          "<td>" + pct(c.model_probability) + "</td>" +
          "<td>" + num(c.fair_odds) + "</td>" +
          "<td>" + num(c.expected_value) + "</td>" +
          '<td><span class="badge ' + riskBadge(c.risk_label) + '">' + (c.risk_label || "") + "</span></td>" +
          "<td>" + c.status + "</td>" +
          "<td>" + (c.result || "") + "</td>" +
          "<td>" + settleButtons("combo", c.id) + "</td>";
        tbody.appendChild(tr);
      });
    }).catch(function (e) { showMessage("Error: " + e.message, "error"); });
  }

  function riskBadge(label) {
    if (label === "low") return "badge-low";
    if (label === "medium") return "badge-medium";
    return "badge-high";
  }

  function loadHistory() {
    if (_historyTab === "combos") { loadCombos(); } else { loadPredictions(); }
  }

  function initHistory() {
    var tabs = document.getElementById("history-tabs");
    if (tabs && !tabs.dataset.bound) {
      tabs.dataset.bound = "1";
      tabs.querySelectorAll(".filter-btn").forEach(function (btn) {
        btn.addEventListener("click", function () {
          tabs.querySelectorAll(".filter-btn").forEach(function (b) { b.classList.remove("active"); });
          btn.classList.add("active");
          _historyTab = btn.getAttribute("data-tab");
          document.getElementById("predictions-panel").hidden = _historyTab !== "predictions";
          document.getElementById("combos-panel").hidden = _historyTab !== "combos";
          loadHistory();
        });
      });
    }
    loadHistory();
  }

  /* --- Aposta.LA + Recommendations --- */
  function coverageBadge(cov) { if (cov === "model" || cov === "heuristic") return "badge-low"; if (cov === "odds_implied_only" || cov === "estimated_only") return "badge-medium"; return "badge-high"; }
  function matchBadge(conf) { conf = Number(conf || 0); if (conf >= 0.85) return { cls: "badge-low", text: "alto " + Math.round(conf * 100) + "%" }; if (conf >= 0.70) return { cls: "badge-medium", text: "medio " + Math.round(conf * 100) + "%" }; return { cls: "badge-high", text: "bajo " + Math.round(conf * 100) + "%" }; }
  function currentMode() { var sel = document.getElementById("rec-mode"); return sel ? sel.value : "balanced"; }
  function readNumber(id) { var el = document.getElementById(id); if (!el || el.value === "") return null; var n = parseFloat(el.value); return isNaN(n) ? null : n; }
  function readText(id) { var el = document.getElementById(id); return el && el.value !== "" ? el.value : null; }
  function recFilters() { var payload = { mode: currentMode(), sync_sources_if_stale: true, force_aposta_refresh: true }; var sport = readText("rec-sport"); if (sport) payload.sport = sport; var league = readText("rec-league"); if (league) payload.league = league; var mp = readNumber("rec-minprob"); if (mp !== null) payload.min_probability = mp; var ev = readNumber("rec-minev"); if (ev !== null) payload.min_ev = ev; var edge = readNumber("rec-minedge"); if (edge !== null) payload.min_edge = edge; var mo = readNumber("rec-minodds"); if (mo !== null) payload.min_odds = mo; var xo = readNumber("rec-maxodds"); if (xo !== null) payload.max_odds = xo; var ml = readNumber("rec-maxlegs"); if (ml !== null) payload.max_legs = parseInt(ml, 10); var ms = readNumber("rec-minsample"); if (ms !== null) payload.min_sample_size = parseInt(ms, 10); var risk = readText("rec-riskmax"); if (risk) payload.risk_max = risk; var cov = readText("rec-coveragemin"); if (cov) payload.coverage_min = cov; payload.max_suggestions = 20; return payload; }
  function syncAposta() { setSyncStatus("Sincronizando Aposta.LA..."); apiPost("/aposta/sync", { force_aposta_refresh: true }).then(function (res) { setSyncStatus("Aposta.LA: " + res.status + " - " + (res.message || "")); showMessage("Aposta.LA sync: " + res.status, res.status === "manual_required" ? "error" : "ok"); loadApostaRuns(); loadApostaOptions(); loadUnmappedMarkets(); }).catch(function (e) { showMessage("Error: " + e.message, "error"); }); }
  function syncApostaAndRecommend() { var btn = document.getElementById("aposta-refresh-btn"); if (btn) btn.setAttribute("disabled", "disabled"); setSyncStatus("Actualizando Aposta.LA y recalculando..."); apiPost("/aposta/sync-and-recommend", recFilters()).then(function (res) { setSyncStatus("Aposta.LA #" + (res.aposta_run_id || "-") + ": " + res.status + " | cuotas " + res.imported_or_captured_odds + " | match " + res.matched_odds + "/" + (res.matched_odds + res.unmatched_odds) + " | simples " + res.singles + " | combinadas " + res.combos); showMessage(res.message || "Recomendaciones actualizadas", res.status === "manual_required" ? "error" : "ok"); var el = document.getElementById("aposta-last-status"); if (el) el.textContent = res.status; loadLatestRecommendations(); loadApostaRuns(); loadApostaOptions(); loadUnmappedMarkets(); }).catch(function (e) { showMessage("Error: " + e.message, "error"); }).finally(function () { if (btn) btn.removeAttribute("disabled"); }); }
  function loadApostaRuns() { var tbody = document.querySelector("#aposta-runs-table tbody"); if (!tbody) return; apiGet("/aposta/sync-runs?limit=30").then(function (rows) { tbody.innerHTML = ""; if (!rows.length) { tbody.innerHTML = "<tr><td colspan=9 class=muted>Sin ejecuciones.</td></tr>"; return; } rows.forEach(function (r) { var tr = document.createElement("tr"); [r.id, r.status, r.parsed_selections || 0, r.mapped_markets || 0, r.unmapped_markets || 0, r.error_count || 0, fmtDate(r.started_at), fmtDate(r.finished_at), r.message || ""].forEach(function (v) { var td = document.createElement("td"); td.textContent = v; tr.appendChild(td); }); tbody.appendChild(tr); }); }).catch(function () {}); }
  function loadApostaOptions() { var tbody = document.querySelector("#aposta-options-table tbody"); if (!tbody) return; apiGet("/aposta/options?limit=100").then(function (rows) { tbody.innerHTML = ""; if (!rows.length) { tbody.innerHTML = "<tr><td colspan=8 class=muted>Colocar CSV en /opt/pirapire/data/imports/aposta o configurar APOSTA_BROWSER_WORKER_URL.</td></tr>"; return; } rows.forEach(function (o) { var tr = document.createElement("tr"); [o.sport, o.competition, o.event, o.market_code || o.market_text, o.selection, num(o.line), num(o.odds_decimal), o.batch_id].forEach(function (v) { var td = document.createElement("td"); td.textContent = v || ""; tr.appendChild(td); }); tbody.appendChild(tr); }); }).catch(function () {}); }
  function loadUnmappedMarkets() { var tbody = document.querySelector("#aposta-unmapped-table tbody"); if (!tbody) return; apiGet("/aposta/unmapped-markets").then(function (rows) { tbody.innerHTML = ""; if (!rows.length) { tbody.innerHTML = "<tr><td colspan=3 class=muted>Sin mercados no mapeados.</td></tr>"; return; } rows.forEach(function (m) { var tr = document.createElement("tr"); [m.sport, m.market_text, m.count].forEach(function (v) { var td = document.createElement("td"); td.textContent = v || ""; tr.appendChild(td); }); tbody.appendChild(tr); }); }).catch(function () {}); }
  function loadLolHistoryStatus() { var box = document.getElementById("lol-history-summary"); var kpis = document.getElementById("lol-history-kpis"); if (!box || !kpis) return; apiGet("/lol-history/status").then(function (s) { box.removeAttribute("hidden"); kpis.innerHTML = ""; ["Ligas " + (s.leagues_count || 0), "Partidas " + (s.games_count || 0), "Equipos " + (s.teams_count || 0), "Jugadores " + (s.players_count || 0)].forEach(function (txt) { var span = document.createElement("span"); span.className = "badge badge-muted"; span.textContent = txt; kpis.appendChild(span); }); var note = document.createElement("span"); note.className = "muted"; note.textContent = s.message || ("Ultimo import: " + fmtDate(s.last_imported_at)); kpis.appendChild(note); }).catch(function () {}); }
  function initAposta() { var el = document.getElementById("aposta-last-status"); apiGet("/aposta/status").then(function (s) { if (el && s.last_run) el.textContent = s.last_run.status; var mode = document.getElementById("aposta-sync-mode"); if (mode) mode.textContent = s.sync_mode || ""; var folder = document.getElementById("aposta-import-dir"); if (folder) folder.textContent = s.host_import_dir || "/opt/pirapire/data/imports/aposta"; }).catch(function () {}); loadApostaRuns(); loadApostaOptions(); loadUnmappedMarkets(); }
  function runRecommendations() { setSyncStatus("Calculando recomendaciones con el ultimo snapshot..."); apiPost("/recommendations/run", recFilters()).then(function (res) { setSyncStatus("Run #" + res.run_id + " (" + res.mode + "): " + res.total_recommendations + " apuestas, " + res.total_combos + " combinadas."); showMessage("Recomendaciones actualizadas (" + res.mode + ")", "ok"); loadLatestRecommendations(); }).catch(function (e) { showMessage("Error: " + e.message, "error"); }); }
  function loadLatestRecommendations() { var label = document.getElementById("rec-mode-label"); if (label) label.textContent = currentMode(); loadRecBets(); loadRecCombos(); loadLolHistoryStatus(); }
  function appendCell(tr, value, className) { var td = document.createElement("td"); if (className) td.className = className; td.textContent = value == null ? "" : value; tr.appendChild(td); }
  function appendBadgeCell(tr, text, cls) { var td = document.createElement("td"); var span = document.createElement("span"); span.className = "badge " + cls; span.textContent = text || ""; td.appendChild(span); tr.appendChild(td); }
  function appendSaveButton(tr, id, combo) { var td = document.createElement("td"); td.className = "table-actions"; var btn = document.createElement("button"); btn.className = "btn btn-outline filter-btn"; btn.textContent = "Guardar"; btn.addEventListener("click", function () { combo ? saveComboRecToHistory(id) : saveRecToHistory(id); }); td.appendChild(btn); tr.appendChild(td); }
  function loadRecBets() { var tbody = document.querySelector("#rec-bets-table tbody"); if (!tbody) return; apiGet("/recommendations/bets?mode=" + currentMode() + "&limit=20").then(function (rows) { tbody.innerHTML = ""; if (!rows.length) { tbody.innerHTML = "<tr><td colspan=15 class=muted>Sin recomendaciones. Colocar CSV en /opt/pirapire/data/imports/aposta y actualizar.</td></tr>"; return; } rows.forEach(function (b) { var mb = matchBadge(b.match_confidence); var tr = document.createElement("tr"); appendCell(tr, b.league || ""); appendCell(tr, b.event_label || "", "event-cell"); appendCell(tr, b.market_code || b.market_text || ""); appendCell(tr, b.selection_text || ""); appendCell(tr, num(b.odds_decimal)); appendCell(tr, pct(b.model_probability)); appendCell(tr, pct(b.implied_probability)); appendCell(tr, num(b.fair_odds)); appendCell(tr, num(b.expected_value)); appendCell(tr, num(b.edge)); appendBadgeCell(tr, mb.text, mb.cls); appendCell(tr, b.sample_size || 0); appendBadgeCell(tr, b.coverage_status || "", coverageBadge(b.coverage_status)); appendCell(tr, b.explanation || b.match_reason || "", "reason-cell"); appendSaveButton(tr, b.id, false); tbody.appendChild(tr); }); }).catch(function (e) { showMessage("Error: " + e.message, "error"); }); }
  function loadRecCombos() { var tbody = document.querySelector("#rec-combos-table tbody"); if (!tbody) return; apiGet("/recommendations/combos?mode=" + currentMode() + "&limit=20").then(function (rows) { tbody.innerHTML = ""; if (!rows.length) { tbody.innerHTML = "<tr><td colspan=7 class=muted>Sin combinadas.</td></tr>"; return; } rows.forEach(function (item) { var c = item.combo; var tr = document.createElement("tr"); appendCell(tr, c.name || "", "name-cell"); appendCell(tr, c.legs_count); appendCell(tr, num(c.offered_odds)); appendCell(tr, pct(c.model_probability)); appendCell(tr, num(c.expected_value)); appendBadgeCell(tr, c.risk_label || "", riskBadge(c.risk_label)); appendSaveButton(tr, c.id, true); tbody.appendChild(tr); }); }).catch(function (e) { showMessage("Error: " + e.message, "error"); }); }
  function saveRecToHistory(id) { apiPost("/recommendations/" + id + "/save-to-history", {}).then(function () { showMessage("Apuesta guardada al historial", "ok"); }).catch(function (e) { showMessage("Error: " + e.message, "error"); }); }
  function saveComboRecToHistory(id) { apiPost("/recommendations/combos/" + id + "/save-to-history", {}).then(function () { showMessage("Combinada guardada al historial", "ok"); }).catch(function (e) { showMessage("Error: " + e.message, "error"); }); }
  function initDashboardRecs() { initAposta(); loadLatestRecommendations(); }
  function initRecommendations() { loadLatestRecommendations(); }
  /* --- Dashboard V2 --- */
  function initDashboardV2() { loadDashboardState(); }

  function loadDashboardState() {
    apiGet("/dashboard/state").then(function(state) {
      renderDataStatus(state);
      if (state.recommendations && state.recommendations.blockers && state.recommendations.blockers.length > 0) {
        renderBlockers(state.recommendations.blockers);
      }
      renderActions(state);
      loadLatestRecommendations();
    }).catch(function(e) { showMessage("Error cargando estado: " + e.message, "error"); });
  }

  function refreshAll() {
    var btn = document.getElementById("main-refresh-btn");
    if (btn) btn.setAttribute("disabled", "disabled");
    setSyncStatus("Actualizando datos y buscando mejores opciones...");
    var payload = recFilters();
    payload.sync_sports_if_stale = true;
    payload.refresh_aposta = true;
    payload.use_latest_snapshot_if_no_new_source = true;
    delete payload.force_aposta_refresh;
    delete payload.sync_sources_if_stale;
    apiPost("/dashboard/refresh", payload).then(function(res) {
      setSyncStatus("Singles: " + (res.singles || 0) + " | Combos: " + (res.combos || 0) + " | Observables: " + (res.observables || 0));
      showMessage(res.message || "Refresco completado", res.status === "error" ? "error" : "ok");
      loadDashboardState();
    }).catch(function(e) { showMessage("Error: " + e.message, "error"); })
    .finally(function() { if (btn) btn.removeAttribute("disabled"); });
  }

  function renderDataStatus(state) {
    var fb = state.football || {};
    var fbEl = document.getElementById("fb-status");
    if (fbEl) fbEl.innerHTML = (fb.stale ? "<span class=\"badge badge-high\">Desactualizado</span> " : "<span class=\"badge badge-ok\">OK</span> ") +
      (fb.competitions || 0) + " comps, " + (fb.future_matches || 0) + " futuros";
    var lo = state.lol || {};
    var loEl = document.getElementById("lol-status");
    if (loEl) loEl.innerHTML = (lo.player_data_available ? "<span class=\"badge badge-ok\">OK</span> " : "<span class=\"badge badge-medium\">Sin jugadores</span> ") +
      (lo.games || 0) + " partidas, " + (lo.teams || 0) + " equipos";
    var ap = state.aposta || {};
    var apEl = document.getElementById("ap-status");
    if (apEl) apEl.innerHTML = (ap.current_odds > 0 ? "<span class=\"badge badge-ok\">" + ap.current_odds + " vigentes</span> " : "<span class=\"badge badge-high\">0 vigentes</span> ") +
      (ap.expired_odds || 0) + " vencidas, " + (ap.historical_odds || 0) + " historicas";
    var rec = state.recommendations || {};
    var recEl = document.getElementById("rec-status");
    if (recEl) recEl.innerHTML = (rec.singles || 0) + " apuestas, " + (rec.combos || 0) + " combinadas" +
      (rec.latest_run ? " (hace " + timeAgo(rec.latest_run) + ")" : "");
  }

  function renderBlockers(blockers) {
    var section = document.getElementById("blockers-section");
    var list = document.getElementById("blockers-list");
    if (!section || !list) return;
    if (!blockers || blockers.length === 0) { section.setAttribute("hidden", ""); return; }
    section.removeAttribute("hidden");
    list.innerHTML = "";
    blockers.forEach(function(b) { var li = document.createElement("li"); li.textContent = b; li.className = "text-error"; list.appendChild(li); });
  }

  function renderActions(state) {
    var section = document.getElementById("actions-section");
    var div = document.getElementById("actions-list");
    if (!section || !div) return;
    var actions = [];
    if ((state.aposta || {}).current_odds === 0) {
      actions.push("Colocar archivo CSV de Aposta.LA con cuotas actuales en /opt/pirapire/data/imports/aposta");
    }
    if ((state.lol || {}).games === 0) {
      actions.push("Colocar archivos CSV de Oracle's Elixir en /opt/pirapire/data/imports/oracles");
    }
    if ((state.football || {}).stale) {
      actions.push("Sincronizar datos de futbol: ir a Datos Futbol y presionar Sincronizar");
    }
    if (actions.length === 0) { section.setAttribute("hidden", ""); return; }
    section.removeAttribute("hidden");
    div.innerHTML = actions.map(function(a) { return "<p class=\"muted\">" + a + "</p>"; }).join("");
  }

  function timeAgo(isoStr) {
    if (!isoStr) return "?";
    var then = new Date(isoStr); var now = new Date();
    var diffMs = now - then; var mins = Math.floor(diffMs / 60000);
    if (mins < 1) return "ahora";
    if (mins < 60) return mins + "min";
    var hours = Math.floor(mins / 60);
    if (hours < 24) return hours + "h";
    return Math.floor(hours / 24) + "d";
  }

  function setSyncStatus(msg) {
    var el = document.getElementById("sync-status");
    if (!el) return;
    el.removeAttribute("hidden");
    el.textContent = msg;
  }


  function loadCalendar(filter) {
    filter = filter || "week";
    var tbody = document.querySelector("#calendar-table tbody");
    if (!tbody) return;
    tbody.innerHTML = '<tr><td colspan="5" class="muted">Cargando calendario...</td></tr>';
    var days = filter === "today" ? 1 : filter === "tomorrow" ? 2 : 7;
    apiGet("/dashboard/calendar?days=" + days).then(function(events) {
      tbody.innerHTML = "";
      if (!events || !events.length) {
        tbody.innerHTML = '<tr><td colspan="5" class="muted">No hay eventos proximos</td></tr>';
        return;
      }
      events.forEach(function(e) {
        var tr = document.createElement("tr");
        var dateStr = e.event_date_display || "Horario pendiente de reconfirmación";
        appendCell(tr, dateStr);
        appendCell(tr, e.competition || "", "comp-cell");
        appendCell(tr, e.team_a || "", "team-cell");
        appendCell(tr, e.team_b || "", "team-cell");
        appendCell(tr, e.markets || 0);
        tbody.appendChild(tr);
      });
    }).catch(function(e) { tbody.innerHTML = '<tr><td colspan="5" class="muted">Error cargando calendario</td></tr>'; });
  }


  /* Dashboard V3 - Auto-load, cards-based */
  function initDashboardV3() {
    loadDashboardV3State();
    loadUpcomingEvents();
    loadBestBets();
  }

  function loadDashboardV3State() {
    apiGet("/dashboard/state").then(function(state) {
      var el;
      el = document.getElementById("st-app"); if (el) el.textContent = "OK";
      el = document.getElementById("st-aposta"); if (el && state.aposta) el.textContent = (state.aposta.current_odds || 0) + " odds";
      el = document.getElementById("st-football"); if (el && state.football) el.textContent = (state.football.total_matches || 0) + " matches";
      el = document.getElementById("st-lol"); if (el && state.lol) el.textContent = (state.lol.games || 0) + " games, " + (state.lol.players || 0) + " players";
    }).catch(function(e) { console.log("State error:", e); });
  }

  function loadUpcomingEvents() {
    var c = document.getElementById("upcoming-events");
    if (!c) return;
    apiGet("/dashboard/calendar?days=7").then(function(events) {
      if (!events || !events.length) { c.innerHTML = "<p class=muted>No hay eventos proximos</p>"; return; }
      c.innerHTML = "";
      events.forEach(function(e) {
        var d = e.event_date_display || "Horario pendiente de reconfirmación";
        var teams = (e.team_a || "?") + " vs " + (e.team_b || "?");
        var meta = (e.competition || "Sin competición") + " · " + d + " · " + (e.markets || 0) + " mercados";
        var card = document.createElement("a");
        card.className = "event-card";
        card.href = "/events/" + (e.event_key || e.event_id || "");
        card.setAttribute("aria-label", teams + "; " + meta);
        var sport = document.createElement("div");
        sport.className = "event-sport";
        sport.textContent = e.sport === "lol" ? "L" : "F";
        var content = document.createElement("div");
        content.className = "event-content";
        var teamNames = document.createElement("div");
        teamNames.className = "event-teams";
        teamNames.textContent = teams;
        var metadata = document.createElement("div");
        metadata.className = "event-meta";
        metadata.textContent = meta;
        content.appendChild(teamNames);
        content.appendChild(metadata);
        card.appendChild(sport);
        card.appendChild(content);
        c.appendChild(card);
      });
    }).catch(function(e) { console.log("Events error:", e); c.innerHTML = "<p class=muted>Error cargando eventos</p>"; });
  }

  function loadBestBets() {
    var c = document.getElementById("best-bets");
    if (!c) return;
    apiGet("/recommendations/bets?mode=balanced&limit=10").then(function(bets) {
      if (!bets || !bets.length) { c.innerHTML = "<p class=muted>No hay oportunidades validadas. El modelo requiere mas datos estadisticos.</p>"; return; }
      var h = "";
      bets.forEach(function(b) {
        h += "<div class=bet-card><div class=bet-event>" + (b.event_label||"") + "</div>";
        h += "<div class=bet-detail>" + (b.market_text||b.market_code||"") + ": <b>" + (b.selection_text||"") + "</b> @ " + num(b.odds_decimal) + "</div>";
        h += "<div class=bet-stats>Prob: " + pct(b.model_probability) + " - EV: " + num(b.expected_value) + " - Muestra: " + (b.sample_size||"?") + "</div>";
        h += "<div class=bet-explanation>" + (b.explanation||"") + "</div></div>";
      });
      c.innerHTML = h;
    }).catch(function(e) { console.log("Bets error:", e); c.innerHTML = "<p class=muted>Error cargando recomendaciones</p>"; });
  }

  function initIntegrationSettings() {
    var loginCard = document.getElementById("config-login-card");
    var section = document.getElementById("integrations-section");
    var form = document.getElementById("config-login-form");
    var logout = document.getElementById("config-logout");
    var csrfToken = "";
    var loginToken = "";

    if (!loginCard || !section || !form) return;

    function integrationMessage(text, kind) {
      var el = document.getElementById("integration-message");
      el.textContent = text;
      el.className = "flash flash-" + (kind || "ok");
      el.removeAttribute("hidden");
    }

    function loginMessage(text) {
      var el = document.getElementById("config-login-message");
      el.textContent = text;
      el.className = "flash flash-error";
      el.removeAttribute("hidden");
    }

    function request(url, options) {
      options = options || {};
      options.headers = options.headers || {};
      if (csrfToken && options.method && options.method !== "GET") {
        options.headers["X-CSRF-Token"] = csrfToken;
      }
      if (options.body) options.headers["Content-Type"] = "application/json";
      return fetch(url, options).then(function (response) {
        return response.json().catch(function () { return {}; }).then(function (body) {
          if (!response.ok) throw new Error(body.detail || "request_failed");
          return body;
        });
      });
    }

    function sourceLabel(source) {
      if (source === "ui") return "Interfaz";
      if (source === "env") return "Entorno";
      if (source === "public_free") return "Clave pública Free v1";
      return "No configurada";
    }

    function statusLabel(value) {
      if (value === "active_accepted_risk") return "Activa — riesgo aceptado";
      if (value === "expired") return "Expirada";
      if (value === "quarantined") return "En cuarentena";
      if (value === "public_free") return "Activa — clave pública Free v1";
      if (value === "success") return "Prueba correcta";
      if (value === "legacy_env") return "Pendiente de migración segura";
      if (value === "failed") return "Prueba fallida";
      return "Sin probar";
    }

    function formatDate(value) {
      if (!value) return "—";
      try { return new Date(value).toLocaleString("es-PY"); } catch (_) { return "—"; }
    }

    function makeText(tag, className, text) {
      var node = document.createElement(tag);
      if (className) node.className = className;
      node.textContent = text;
      return node;
    }

    function renderProvider(provider) {
      var card = document.createElement("article");
      card.className = "integration-card";
      card.dataset.provider = provider.slug;
      card.appendChild(makeText("h3", "", provider.name));
      card.appendChild(makeText("p", "muted", provider.description));
      if (provider.data_role) card.appendChild(makeText("p", "integration-role", provider.data_role));
      if (provider.mode) card.appendChild(makeText("span", "badge badge-muted", provider.mode));
      if (provider.rate_limit) card.appendChild(makeText("p", "muted integration-limit", "Límite: " + provider.rate_limit));
      var coverage = Object.keys(provider.coverage || {}).map(function (key) { return key + ": " + provider.coverage[key]; }).join(" · ");
      if (coverage) card.appendChild(makeText("p", "muted integration-limit", "Cobertura: " + coverage));
      if (provider.operational_state) {
        card.appendChild(makeText("p", "muted integration-limit", "Job: " + provider.operational_state.status + " · requests: " + provider.operational_state.request_count + " · filas: " + provider.operational_state.records_processed));
      }
      if (provider.warning) card.appendChild(makeText("p", "flash flash-warning integration-warning", provider.warning));
      if (!provider.requires_key) {
        card.appendChild(makeText("span", "badge badge-ok", "No requiere API key"));
        return card;
      }
      var credential = provider.credentials[0];
      if (credential.risk_accepted) {
        card.appendChild(makeText("p", "flash flash-warning integration-warning", "Credencial activa por decisión explícita del administrador. Se mantiene cifrada y puede reemplazarse en cualquier momento."));
      }
      var status = document.createElement("dl");
      status.className = "integration-status";
      var effectiveStatus = credential.risk_accepted ? "active_accepted_risk" : (credential.source === "public_free" ? "public_free" : credential.test_status);
      [["Fuente efectiva", sourceLabel(credential.source)], ["Estado", statusLabel(effectiveStatus)], ["Última prueba", formatDate(credential.latest_test_at || credential.tested_at)], ["Último uso", formatDate(credential.last_used_at)], ["Expira", formatDate(credential.expires_at)], ["Último error", credential.error_code || credential.latest_test_error_code || "—"]].forEach(function (pair) {
        status.appendChild(makeText("dt", "", pair[0]));
        status.appendChild(makeText("dd", "", pair[1]));
      });
      card.appendChild(status);
      var field = document.createElement("label");
      field.className = "form-field integration-secret";
      field.appendChild(makeText("span", "", "Nueva API key"));
      var input = document.createElement("input");
      input.type = "password";
      input.autocomplete = "new-password";
      input.placeholder = credential.configured && credential.last4 ? "Configurada ••••" + credential.last4 : "No configurada";
      input.setAttribute("aria-label", "Nueva credencial para " + provider.name);
      field.appendChild(input);
      card.appendChild(field);
      var riotMetadata = null;
      if (provider.slug === "riot_api") {
        riotMetadata = {};
        var keyType = document.createElement("select");
        [["personal", "Personal (recomendada)"], ["development", "Development (24 horas)"]].forEach(function (option) {
          var node = document.createElement("option");
          node.value = option[0]; node.textContent = option[1]; keyType.appendChild(node);
        });
        keyType.value = credential.key_type || "personal";
        var typeField = makeText("label", "form-field integration-secret", "Tipo de key");
        typeField.appendChild(keyType); card.appendChild(typeField);
        var platform = document.createElement("select");
        ["la2", "la1", "br1", "na1", "euw1", "eun1", "kr", "jp1", "oc1"].forEach(function (value) {
          var node = document.createElement("option"); node.value = value; node.textContent = value.toUpperCase(); platform.appendChild(node);
        });
        platform.value = credential.default_platform || "la2";
        var platformField = makeText("label", "form-field integration-secret", "Plataforma predeterminada");
        platformField.appendChild(platform); card.appendChild(platformField);
        var region = document.createElement("select");
        ["americas", "europe", "asia", "sea"].forEach(function (value) {
          var node = document.createElement("option"); node.value = value; node.textContent = value; region.appendChild(node);
        });
        region.value = credential.regional_routes[0] || "americas";
        var regionField = makeText("label", "form-field integration-secret", "Ruta regional");
        regionField.appendChild(region); card.appendChild(regionField);
        riotMetadata = {keyType:keyType, platform:platform, region:region};
      }
      var actions = document.createElement("div");
      actions.className = "integration-actions";
      function button(label, className, handler) {
        var btn = makeText("button", "btn " + className, label);
        btn.type = "button";
        btn.addEventListener("click", handler);
        actions.appendChild(btn);
      }
      button("Probar", "btn-secondary", function () {
        if (!input.value) return integrationMessage("Ingresa un candidato para probar.", "error");
        var candidate = input.value;
        request("/api/settings/integrations/" + provider.slug + "/test", {method:"POST", body:JSON.stringify({value:candidate})})
          .then(function () { integrationMessage("Prueba correcta. El candidato aún no fue guardado.", "ok"); })
          .catch(function () { integrationMessage("La prueba falló. La credencial vigente no cambió.", "error"); })
          .finally(function () { candidate = ""; input.value = ""; });
      });
      button("Guardar nueva", "btn-primary", function () {
        if (!input.value || !window.confirm("¿Probar y reemplazar el override de " + provider.name + "?")) return;
        var candidate = input.value;
        var payload = {value:candidate};
        if (riotMetadata) {
          payload.key_type = riotMetadata.keyType.value;
          payload.default_platform = riotMetadata.platform.value;
          payload.regional_routes = [riotMetadata.region.value];
        }
        request("/api/settings/integrations/" + provider.slug + "/credentials/" + credential.name, {method:"PUT", body:JSON.stringify(payload)})
          .then(function () { integrationMessage("Credencial probada y guardada de forma cifrada.", "ok"); return loadIntegrations(); })
          .catch(function () { integrationMessage("No se guardó: la prueba del candidato falló.", "error"); })
          .finally(function () { candidate = ""; input.value = ""; });
      });
      if (credential.source === "ui") {
        button("Eliminar override", "btn-danger", function () {
          if (!window.confirm("¿Eliminar el override? Puede volver al fallback de entorno.")) return;
          request("/api/settings/integrations/" + provider.slug + "/credentials/" + credential.name, {method:"DELETE"})
            .then(function () { integrationMessage("Override eliminado.", "ok"); return loadIntegrations(); })
            .catch(function () { integrationMessage("No se pudo eliminar el override.", "error"); });
        });
      }
      card.appendChild(actions);
      return card;
    }

    function loadIntegrations() {
      return request("/api/settings/integrations", {method:"GET"}).then(function (data) {
        var cards = document.getElementById("integration-cards");
        cards.innerHTML = "";
        data.providers.forEach(function (provider) { cards.appendChild(renderProvider(provider)); });
      });
    }

    function showAuthenticated(token) {
      csrfToken = token;
      loginCard.setAttribute("hidden", "");
      section.removeAttribute("hidden");
      return loadIntegrations();
    }

    request("/api/settings/auth/status", {method:"GET"})
      .then(function (data) {
        if (data.authenticated) return showAuthenticated(data.csrf_token);
        return request("/api/settings/auth/bootstrap", {method:"GET"}).then(function (bootstrap) { loginToken = bootstrap.csrf_token; });
      })
      .catch(function () { loginMessage("No se pudo iniciar el módulo de integraciones."); });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      var password = document.getElementById("config-admin-password");
      var candidate = password.value;
      request("/api/settings/auth/login", {method:"POST", body:JSON.stringify({password:candidate, csrf_token:loginToken})})
        .then(function (data) { password.value = ""; candidate = ""; return showAuthenticated(data.csrf_token); })
        .catch(function () { password.value = ""; candidate = ""; loginMessage("Acceso administrativo rechazado."); });
    });

    logout.addEventListener("click", function () {
      request("/api/settings/auth/logout", {method:"POST"}).finally(function () { window.location.reload(); });
    });
  }

  return { showMessage: showMessage, apiGet: apiGet, apiPost: apiPost, renderTable: renderTable, initTopClock: initTopClock, initDashboard: initDashboard, initSports: initSports, initTeams: initTeams, initMatches: initMatches, initOdds: initOdds, initCombo: initCombo, initTheme: initTheme, applyTheme: applyTheme, toggleTheme: toggleTheme, syncSource: syncSource, recalcRanking: recalcRanking, loadSourceRuns: loadSourceRuns, initSourceRuns: initSourceRuns, initDataFootball: initDataFootball, initDataLol: initDataLol, initMarkets: initMarkets, reseedMarkets: reseedMarkets, initImports: initImports, initHistory: initHistory, loadHistory: loadHistory, settlePrediction: settlePrediction, settleCombo: settleCombo, syncAposta: syncAposta, syncApostaAndRecommend: syncApostaAndRecommend, loadApostaRuns: loadApostaRuns, loadApostaOptions: loadApostaOptions, loadUnmappedMarkets: loadUnmappedMarkets, initIntegrationSettings: initIntegrationSettings, loadRecBets: loadRecBets, loadRecCombos: loadRecCombos, saveRecToHistory: saveRecToHistory, saveComboRecToHistory: saveComboRecToHistory, initDashboardRecs: initDashboardRecs, initRecommendations: initRecommendations, initDashboardV2: initDashboardV2, refreshAll: refreshAll, loadDashboardState: loadDashboardState, loadCalendar: loadCalendar, initDashboardV3: initDashboardV3, loadBestBets: loadBestBets, loadUpcomingEvents: loadUpcomingEvents };

  document.addEventListener("DOMContentLoaded", function() {
    try { initTopClock(); initTheme(); } catch(e) {}
  });
})();
