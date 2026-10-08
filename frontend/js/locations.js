/**
 * UrbanPulse – Police Locations Renderer
 * Reads from window.UP_POLICE (set by data.js).
 * Renders police KPI cards, donut chart, and table for analytics.html.
 */
(function () {
  "use strict";

  var COLORS = ["#38bdf8", "#f59e0b", "#10b981", "#8b5cf6", "#f43f5e", "#6366f1"];

  function $ (id) { return document.getElementById(id); }

  function renderPoliceKPIs(data) {
    var grid = $("cx-police-kpis");
    if (!grid) return;
    var byType = data.by_type || [];
    var icons = { "Police Station": "🚔", "Police Outpost": "🏢" };
    grid.innerHTML = [
      { title: "Total Locations", value: data.total || 0, icon: "📍", color: "var(--accent-cyan)" }
    ].concat(byType.map(function (t) {
      return { title: t.type, value: t.count, icon: icons[t.type] || "📌", color: "var(--accent-amber)" };
    })).map(function (card) {
      return "<div class='kpi-card glass-panel'>" +
        "<div class='kpi-header'><span class='kpi-title'>" + card.title + "</span>" +
        "<div class='kpi-icon' style='color:" + card.color + "'>" + card.icon + "</div></div>" +
        "<div class='kpi-value' style='color:" + card.color + "'>" + card.value + "</div>" +
        "<div class='kpi-subtext'>Verified KML records</div></div>";
    }).join("");
  }

  function renderPoliceDonut(data) {
    var canvas = $("cx-police-donut");
    if (!canvas || typeof Chart === "undefined") return;
    var byType = data.by_type || [];
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: byType.map(function (t) { return t.type; }),
        datasets: [{
          data: byType.map(function (t) { return t.count; }),
          backgroundColor: COLORS.slice(0, byType.length),
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

  function renderPoliceTable(data) {
    var tbody = $("cx-police-table");
    if (!tbody) return;
    var byType = data.by_type || [];
    tbody.innerHTML = byType.map(function (t) {
      return "<tr><td>" + t.type + "</td><td>" + t.count + "</td><td><code style='font-size:11px'>" + (t.source_kml || "—") + "</code></td></tr>";
    }).join("") || "<tr><td colspan='3'>No data.</td></tr>";
  }

  document.addEventListener("DOMContentLoaded", function () {
    var data = window.UP_POLICE || {};
    try { renderPoliceKPIs(data); } catch (e) { console.error("[Police] KPIs:", e); }
    try { renderPoliceDonut(data); } catch (e) { console.error("[Police] Donut:", e); }
    try { renderPoliceTable(data); } catch (e) { console.error("[Police] Table:", e); }
  });

})();
