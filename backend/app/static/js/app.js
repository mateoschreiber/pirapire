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
  };
})();
