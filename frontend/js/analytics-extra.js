/**
 * UrbanPulse – Analytics Extra Charts
 * Renders the 2021–2023 crime comparison charts and year-table.
 * All values from window.UP_CRIME (set by data.js).
 * Also handles analytics tab switching and ESG demo year-wise data injection.
 */
(function () {
  "use strict";

  var COLORS = {
    women:      "#f43f5e",
    children:   "#f59e0b",
    cyber:      "#6366f1",
    suicides:   "#8b5cf6",
    accidental: "#38bdf8"
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

  // ─── Analytics Tab Switch ──────────────────────────────────────────────────
  function initTabSwitcher() {
    var tabs = document.querySelectorAll(".analytics-tabs .category-pill");
    var panels = document.querySelectorAll(".analytics-tab-panel");
    tabs.forEach(function (tab) {
      tab.addEventListener("click", function () {
        tabs.forEach(function (t) { t.classList.remove("active"); t.setAttribute("aria-selected", "false"); });
        panels.forEach(function (p) { p.classList.remove("active"); });
        tab.classList.add("active");
        tab.setAttribute("aria-selected", "true");
        var tabName = tab.getAttribute("data-tab");
        var targetId = "tab-" + tabName;
        var panel = document.getElementById(targetId);
        if (panel) panel.classList.add("active");

        if (tabName === "construction" && typeof window.initUrbanPulseConstructionAnalytics === "function") {
          window.initUrbanPulseConstructionAnalytics();
        } else if (tabName === "crime" && typeof window.initUrbanPulseCrimeAnalytics === "function") {
          window.initUrbanPulseCrimeAnalytics();
        }
      });
    });
  }

  // ─── 2021–2023 Comparison Charts ──────────────────────────────────────────
  function renderCasesLine() {
    var canvas = $("cx-crime-cases-line");
    if (!canvas || typeof Chart === "undefined") return;
    var crime = window.UP_CRIME || {};
    var cats = crime.categories || {};
    var years = [2021, 2022, 2023];
    var women     = cats.women     && cats.women.by_year     || [];
    var children  = cats.children  && cats.children.by_year  || [];
    var cyber     = cats.cyber     && cats.cyber.by_year     || [];

    function byYr(arr, field) {
      return years.map(function (y) { var r = arr.find(function (x) { return x.year === y; }); return r ? r[field || "cases"] : null; });
    }

    new Chart(canvas, {
      type: "line",
      data: {
        labels: years,
        datasets: [
          { label: "Women Crimes", data: byYr(women, "cases"), borderColor: COLORS.women, backgroundColor: "rgba(244,63,94,0.1)", tension: 0.4, fill: true, pointRadius: 5 },
          { label: "Children Crimes", data: byYr(children, "cases"), borderColor: COLORS.children, backgroundColor: "rgba(245,158,11,0.1)", tension: 0.4, fill: true, pointRadius: 5 },
          { label: "Cyber Crimes", data: byYr(cyber, "cases"), borderColor: COLORS.cyber, backgroundColor: "rgba(99,102,241,0.1)", tension: 0.4, fill: true, pointRadius: 5 }
        ]
      },
      options: Object.assign({}, CHART_DEFAULTS, {
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { position: "bottom", labels: { color: "#e2e8f0" } } })
      })
    });
  }

  function renderDeathsBar() {
    var canvas = $("cx-crime-deaths-bar");
    if (!canvas || typeof Chart === "undefined") return;
    var crime = window.UP_CRIME || {};
    var cats = crime.categories || {};
    var years = [2021, 2022, 2023];
    var suicides   = cats.suicides   && cats.suicides.by_year   || [];
    var accidental = cats.accidental && cats.accidental.by_year || [];

    function byYr(arr, field) {
      return years.map(function (y) { var r = arr.find(function (x) { return x.year === y; }); return r ? r[field || "deaths"] : null; });
    }

    new Chart(canvas, {
      type: "bar",
      data: {
        labels: years,
        datasets: [
          { label: "Suicides", data: byYr(suicides, "deaths"), backgroundColor: COLORS.suicides, borderRadius: 4 },
          { label: "Accidental Deaths", data: byYr(accidental, "deaths"), backgroundColor: COLORS.accidental, borderRadius: 4 }
        ]
      },
      options: Object.assign({}, CHART_DEFAULTS, {
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { position: "bottom", labels: { color: "#e2e8f0" } } })
      })
    });
  }

  function renderFatalDonut() {
    var canvas = $("cx-crime-fatal-donut");
    if (!canvas || typeof Chart === "undefined") return;
    var overall = (window.UP_CRIME || {}).overall || {};
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["Non-Fatal", "Fatal"],
        datasets: [{
          data: [overall.non_fatal || 0, overall.fatal || 0],
          backgroundColor: ["#38bdf8", "#ef4444"],
          borderColor: "#0a0e17",
          borderWidth: 3,
          hoverOffset: 10
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: "65%",
        plugins: { legend: { position: "bottom", labels: { color: "#e2e8f0", font: { size: 12 } } } }
      }
    });
  }

  function renderCyberDonut() {
    var canvas = $("cx-crime-cyber-donut");
    if (!canvas || typeof Chart === "undefined") return;
    var cyber = (((window.UP_CRIME || {}).categories || {}).cyber || {});
    var divs = cyber.by_division_2023 || [];
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: divs.map(function (d) { return d.division; }),
        datasets: [{
          data: divs.map(function (d) { return d.cases; }),
          backgroundColor: ["#6366f1", "#38bdf8", "#10b981", "#f59e0b", "#f43f5e"],
          borderColor: "#0a0e17",
          borderWidth: 3,
          hoverOffset: 10
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: "65%",
        plugins: { legend: { position: "bottom", labels: { color: "#e2e8f0", font: { size: 12 } } } }
      }
    });
  }

  function renderYearTable() {
    var tbody = $("cx-crime-year-table");
    if (!tbody) return;
    var crime = window.UP_CRIME || {};
    var cats = crime.categories || {};
    var years = [2021, 2022, 2023];

    function val(arr, yr, field) {
      var r = (arr || []).find(function (x) { return x.year === yr; });
      return r ? (r[field] != null ? r[field].toLocaleString("en-IN") : "—") : "—";
    }

    var rows = [
      { label: "Women Crimes",      arr: (cats.women || {}).by_year || [],      field: "cases",  measure: "Reported Cases" },
      { label: "Children Crimes",   arr: (cats.children || {}).by_year || [],    field: "cases",  measure: "Reported Cases" },
      { label: "Cyber Crimes",      arr: (cats.cyber || {}).by_year || [],       field: "cases",  measure: "Reported Cases" },
      { label: "Suicides",          arr: (cats.suicides || {}).by_year || [],    field: "deaths", measure: "Deaths" },
      { label: "Accidental Deaths", arr: (cats.accidental || {}).by_year || [],  field: "deaths", measure: "Deaths" }
    ];

    tbody.innerHTML = rows.map(function (row) {
      return "<tr><td>" + row.label + "</td>" +
        years.map(function (y) { return "<td>" + val(row.arr, y, row.field) + "</td>"; }).join("") +
        "<td><em>" + row.measure + "</em></td></tr>";
    }).join("");
  }

  // ─── Run ───────────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    initTabSwitcher();
    try { renderCasesLine(); }    catch(e) { console.error("[AnalyticsExtra] Cases line:", e); }
    try { renderDeathsBar(); }    catch(e) { console.error("[AnalyticsExtra] Deaths bar:", e); }
    try { renderFatalDonut(); }   catch(e) { console.error("[AnalyticsExtra] Fatal donut:", e); }
    try { renderCyberDonut(); }   catch(e) { console.error("[AnalyticsExtra] Cyber donut:", e); }
    try { renderYearTable(); }    catch(e) { console.error("[AnalyticsExtra] Year table:", e); }
  });

})();
