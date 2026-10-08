/**
 * UrbanPulse – Crime Analytics Renderer
 * Reads from window.UP_CRIME (set by data.js).
 * Renders all crime charts, tables, risk gauge for analytics.html.
 */
(function () {
  "use strict";

  var COLORS = {
    red:    "#ef4444",
    amber:  "#f59e0b",
    cyan:   "#38bdf8",
    emerald:"#10b981",
    purple: "#8b5cf6",
    rose:   "#f43f5e",
    indigo: "#6366f1"
  };

  var CHART_DEFAULTS = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: "#e2e8f0", font: { family: "Inter, sans-serif", size: 12 } } } },
    scales: {
      x: { ticks: { color: "#94a3b8", font: { size: 11 } }, grid: { color: "rgba(255,255,255,0.06)" } },
      y: { ticks: { color: "#94a3b8", font: { size: 11 } }, grid: { color: "rgba(255,255,255,0.06)" } }
    }
  };

  function $ (id) { return document.getElementById(id); }
  function setText(id, val) { var el = $(id); if (el) el.textContent = val; }
  function fmt(n) { return typeof n === "number" ? n.toLocaleString("en-IN") : "—"; }

  var _charts = {};

  function destroyChart(id) {
    if (_charts[id]) { try { _charts[id].destroy(); } catch(e) {} delete _charts[id]; }
  }

  function makeChart(id, config) {
    destroyChart(id);
    var canvas = $(id);
    if (!canvas || typeof Chart === "undefined") return;
    _charts[id] = new Chart(canvas, config);
  }

  // Render the annual D47 trend chart
  function renderTrendChart() {
    var rows = (window.UP_CRIME && window.UP_CRIME.d47_annual) || [];
    makeChart("crime-trend-chart", {
      type: "bar",
      data: {
        labels: rows.map(function (r) { return r.year; }),
        datasets: [
          {
            label: "Non-Fatal Crimes",
            data: rows.map(function (r) { return r.total - r.fatal; }),
            backgroundColor: COLORS.cyan,
            borderRadius: 4
          },
          {
            label: "Fatal Crimes",
            data: rows.map(function (r) { return r.fatal; }),
            backgroundColor: COLORS.red,
            borderRadius: 4
          }
        ]
      },
      options: Object.assign({}, CHART_DEFAULTS, {
        scales: Object.assign({}, CHART_DEFAULTS.scales, {
          x: Object.assign({}, CHART_DEFAULTS.scales.x),
          y: Object.assign({}, CHART_DEFAULTS.scales.y, { stacked: false })
        }),
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { position: "bottom", labels: { color: "#e2e8f0", font: { size: 12 } } } })
      })
    });
  }

  // Render category breakdown chart and table for a given category + year
  function renderCategoryView(category, year) {
    var crime = window.UP_CRIME || {};
    var cats = crime.categories || {};
    var note = $("crime-source-note");
    var chartTitle = $("crime-chart-heading");
    var tableTitle = $("crime-table-title");

    if (category === "all") {
      var rows = cats.all || [];
      setText("kpi-label-total", "Total Crimes (2014–2021)");
      setText("kpi-label-fatal", "Fatal Crimes");
      setText("kpi-label-nonfatal", "Non-Fatal Crimes");
      setText("kpi-label-rate", "Fatal Severity %");
      setText("kpi-total-crimes", fmt((crime.overall || {}).total));
      setText("kpi-fatal-crimes", fmt((crime.overall || {}).fatal));
      setText("kpi-nonfatal-crimes", fmt((crime.overall || {}).non_fatal));
      setText("kpi-detection-rate", ((crime.overall || {}).fatal_pct || 0).toFixed(2) + "%");
      if (note) note.textContent = "Source: Bengaluru City Police D47 Series (2014–2021). Verified EDA only.";
      if (chartTitle) chartTitle.textContent = "📊 Crime Type Distribution (2014–2021 Total)";
      if (tableTitle) tableTitle.textContent = "Bengaluru City-Wide Crime Totals (Verified D47 EDA)";

      makeChart("crime-category-chart", {
        type: "bar",
        data: {
          labels: rows.map(function (r) { return r.crime_type; }),
          datasets: [{
            label: "Reported Cases",
            data: rows.map(function (r) { return r.reported; }),
            backgroundColor: COLORS.cyan,
            borderRadius: 4
          }]
        },
        options: Object.assign({}, CHART_DEFAULTS, {
          indexAxis: "y",
          plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { display: false } })
        })
      });

      var tbody = $("crime-data-table-body");
      if (tbody) {
        var col1 = $("table-col-1"), col2 = $("table-col-2"), col3 = $("table-col-3"), col4 = $("table-col-4");
        if (col1) col1.textContent = "Crime Type";
        if (col2) col2.textContent = "Reported Cases";
        if (col3) col3.textContent = "Fatal";
        if (col4) col4.textContent = "Fatal Rate";
        tbody.innerHTML = rows.map(function (r) {
          return "<tr><td>" + r.crime_type + "</td><td>" + fmt(r.reported) + "</td><td>" +
            (r.detected_fatal != null ? fmt(r.detected_fatal) : "<em>n/a</em>") + "</td><td>" +
            (r.rate_pct != null ? r.rate_pct.toFixed(1) + "%" : "<em>n/a</em>") + "</td></tr>";
        }).join("") || "<tr><td colspan='4'>No data.</td></tr>";
      }

    } else if (category === "women" || category === "children") {
      var cat = cats[category] || {};
      var byYear = cat.by_year || [];
      var subtypes = category === "women" ? (cat.subtypes_2023 || []) : (cat.subtypes_2023 || []);
      var label = category === "women" ? "Crimes Against Women" : "Crimes Against Children";

      setText("kpi-label-total", label + " Total (2021-23)");
      setText("kpi-label-fatal", "2023 Cases");
      setText("kpi-label-nonfatal", "2022 Cases");
      setText("kpi-label-rate", "YoY Change");
      var total = byYear.reduce(function (s, r) { return s + r.cases; }, 0);
      var yr2023 = (byYear.find(function (r) { return r.year === 2023; }) || {}).cases || 0;
      var yr2022 = (byYear.find(function (r) { return r.year === 2022; }) || {}).cases || 0;
      var yr2021 = (byYear.find(function (r) { return r.year === 2021; }) || {}).cases || 0;
      var yoy = yr2022 ? (((yr2023 - yr2022) / yr2022) * 100).toFixed(1) + "%" : "—";
      setText("kpi-total-crimes", fmt(total));
      setText("kpi-fatal-crimes", fmt(yr2023));
      setText("kpi-nonfatal-crimes", fmt(yr2022));
      setText("kpi-detection-rate", yoy);
      if (note) note.textContent = "Source: " + cat.source + ". Year: " + year;
      if (chartTitle) chartTitle.textContent = "📊 " + label + " — Sub-type Breakdown (2023)";

      makeChart("crime-category-chart", {
        type: "bar",
        data: {
          labels: subtypes.map(function (s) { return s.type; }),
          datasets: [{
            label: "2023 Cases",
            data: subtypes.map(function (s) { return s.cases; }),
            backgroundColor: category === "women" ? COLORS.rose : COLORS.amber,
            borderRadius: 4
          }]
        },
        options: Object.assign({}, CHART_DEFAULTS, {
          indexAxis: "y",
          plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { display: false } })
        })
      });

      var tbody2 = $("crime-data-table-body");
      if (tbody2) {
        var col1b = $("table-col-1"), col2b = $("table-col-2"), col3b = $("table-col-3"), col4b = $("table-col-4");
        if (col1b) col1b.textContent = "Year";
        if (col2b) col2b.textContent = "Cases";
        if (col3b) col3b.textContent = "—";
        if (col4b) col4b.textContent = "—";
        tbody2.innerHTML = byYear.map(function (r) {
          return "<tr><td>" + r.year + "</td><td>" + fmt(r.cases) + "</td><td>—</td><td>—</td></tr>";
        }).join("");
      }

    } else if (category === "cyber") {
      var cat2 = cats.cyber || {};
      var byYear2 = cat2.by_year || [];
      var byDiv = cat2.by_division_2023 || [];
      var yr2023b = (byYear2.find(function (r) { return r.year === 2023; }) || {}).cases || 0;
      var yr2022b = (byYear2.find(function (r) { return r.year === 2022; }) || {}).cases || 0;
      var yoy2 = yr2022b ? (((yr2023b - yr2022b) / yr2022b) * 100).toFixed(1) + "%" : "—";
      setText("kpi-label-total", "Cyber Crimes Total (2021-23)");
      setText("kpi-label-fatal", "2023 Cases");
      setText("kpi-label-nonfatal", "2022 Cases");
      setText("kpi-label-rate", "YoY Change (22→23)");
      setText("kpi-total-crimes", fmt(byYear2.reduce(function (s, r) { return s + r.cases; }, 0)));
      setText("kpi-fatal-crimes", fmt(yr2023b));
      setText("kpi-nonfatal-crimes", fmt(yr2022b));
      setText("kpi-detection-rate", yoy2);
      if (note) note.textContent = "Source: " + cat2.source + ".";
      if (chartTitle) chartTitle.textContent = "📊 Cyber Crime by Division (2023)";
      makeChart("crime-category-chart", {
        type: "bar",
        data: {
          labels: byDiv.map(function (d) { return d.division; }),
          datasets: [{
            label: "2023 Cases",
            data: byDiv.map(function (d) { return d.cases; }),
            backgroundColor: COLORS.indigo,
            borderRadius: 4
          }]
        },
        options: Object.assign({}, CHART_DEFAULTS, {
          plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { display: false } })
        })
      });

    } else if (category === "suicides" || category === "accidental") {
      var cat3 = cats[category] || {};
      var byYear3 = cat3.by_year || [];
      var key = category === "suicides" ? "deaths" : "deaths";
      var label3 = category === "suicides" ? "Suicides" : "Accidental Deaths";
      setText("kpi-label-total", label3 + " Total (2021-23)");
      setText("kpi-label-fatal", "2023");
      setText("kpi-label-nonfatal", "2022");
      setText("kpi-label-rate", "YoY 22→23");
      var y23 = (byYear3.find(function (r) { return r.year === 2023; }) || {})[key] || 0;
      var y22 = (byYear3.find(function (r) { return r.year === 2022; }) || {})[key] || 0;
      var yoyD = y22 ? (((y23 - y22) / y22) * 100).toFixed(1) + "%" : "—";
      setText("kpi-total-crimes", fmt(byYear3.reduce(function (s, r) { return s + (r[key] || 0); }, 0)));
      setText("kpi-fatal-crimes", fmt(y23));
      setText("kpi-nonfatal-crimes", fmt(y22));
      setText("kpi-detection-rate", yoyD);
      if (note) note.textContent = "Source: " + cat3.source + ".";
      if (chartTitle) chartTitle.textContent = "📊 " + label3 + " by Year";
      makeChart("crime-category-chart", {
        type: "bar",
        data: {
          labels: byYear3.map(function (r) { return r.year; }),
          datasets: [{
            label: label3,
            data: byYear3.map(function (r) { return r[key]; }),
            backgroundColor: COLORS.rose,
            borderRadius: 4
          }]
        },
        options: Object.assign({}, CHART_DEFAULTS, {
          plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { display: false } })
        })
      });
    }
  }

  function init() {
    renderTrendChart();
    renderCategoryView("all", "2023");

    // Tab pill interactions for crime categories
    var pills = document.querySelectorAll(".analytics-tab-panel#tab-crime .category-pill:not(.disabled)");
    pills.forEach(function (pill) {
      pill.addEventListener("click", function () {
        pills.forEach(function (p) { p.classList.remove("active"); });
        pill.classList.add("active");
        var cat = pill.getAttribute("data-category") || "all";
        var yearSel = $("crime-year-select");
        renderCategoryView(cat, yearSel ? yearSel.value : "2023");
      });
    });

    var yearSel = $("crime-year-select");
    if (yearSel) {
      yearSel.addEventListener("change", function () {
        var activeP = document.querySelector(".analytics-tab-panel#tab-crime .category-pill.active:not(.disabled)");
        renderCategoryView(activeP ? (activeP.getAttribute("data-category") || "all") : "all", yearSel.value);
      });
    }
  }

  window.initUrbanPulseCrimeAnalytics = init;

})();
