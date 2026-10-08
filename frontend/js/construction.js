/**
 * UrbanPulse – Construction Analytics Renderer
 * Reads from window.URBANPULSE_CONSTRUCTION_DATA (set by construction-data.js).
 * Renders all construction charts and tables on analytics.html.
 */
(function () {
  "use strict";

  var COLORS = {
    amber: "#f59e0b",
    cyan:  "#38bdf8",
    emerald: "#10b981",
    purple: "#8b5cf6",
    rose: "#f43f5e",
    indigo: "#6366f1",
    neutral: "rgba(255,255,255,0.12)"
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
  function fmt(n, decimals) { return typeof n === "number" ? n.toFixed(decimals || 0) : "—"; }
  function fmtCr(cr) { return cr != null ? "₹" + fmt(cr, 2) + " Cr" : "—"; }

  function renderOverviewKPIs(d) {
    var o = d.overview || {};
    var el;
    el = $("cx-kpi-net");   if (el) el.textContent = fmtCr(o.net_expenditure_cr);
    el = $("cx-kpi-ded");   if (el) el.textContent = fmtCr(o.total_deductions_cr);
    el = $("cx-kpi-avg");   if (el) el.textContent = o.avg_amount_per_order_lakh ? "₹" + fmt(o.avg_amount_per_order_lakh, 2) + " L" : "—";
  }

  function renderBudgetDonut(d) {
    var canvas = $("cx-budget-donut");
    if (!canvas || typeof Chart === "undefined") return;
    var o = d.overview || {};
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: ["Net Expenditure", "Deductions"],
        datasets: [{
          data: [o.net_expenditure_cr || 0, o.total_deductions_cr || 0],
          backgroundColor: [COLORS.emerald, COLORS.rose],
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

  function renderClusterDonut(d) {
    var canvas = $("cx-cluster-donut");
    if (!canvas || typeof Chart === "undefined") return;
    var clusters = (d.clustering && d.clustering.clusters) || [];
    new Chart(canvas, {
      type: "doughnut",
      data: {
        labels: clusters.map(function (c) { return c.label.split(" / ")[0]; }),
        datasets: [{
          data: clusters.map(function (c) { return c.wards; }),
          backgroundColor: [COLORS.amber, COLORS.cyan],
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

  function renderTopOrdersChart(d) {
    var canvas = $("cx-top-orders");
    if (!canvas || typeof Chart === "undefined") return;
    var wards = (d.top_wards || []).slice(0, 10);
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: wards.map(function (w) { return w.ward; }),
        datasets: [{
          label: "Work Orders",
          data: wards.map(function (w) { return w.orders; }),
          backgroundColor: COLORS.cyan,
          borderRadius: 6
        }]
      },
      options: Object.assign({}, CHART_DEFAULTS, {
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { display: false } }),
        scales: Object.assign({}, CHART_DEFAULTS.scales, {
          x: Object.assign({}, CHART_DEFAULTS.scales.x, { ticks: { color: "#94a3b8", maxRotation: 40, font: { size: 10 } } })
        })
      })
    });
  }

  function renderWardHistogram(d) {
    var canvas = $("cx-ward-hist");
    if (!canvas || typeof Chart === "undefined") return;
    var bins = d.ward_histogram || [];
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: bins.map(function (b) { return b.bin; }),
        datasets: [{
          label: "Wards",
          data: bins.map(function (b) { return b.count; }),
          backgroundColor: COLORS.purple,
          borderRadius: 6
        }]
      },
      options: Object.assign({}, CHART_DEFAULTS, {
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { display: false } })
      })
    });
  }

  function renderInvestmentChart(d) {
    var canvas = $("construction-investment-chart");
    if (!canvas || typeof Chart === "undefined") return;
    var wards = (d.top_wards || []).slice(0, 10);
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: wards.map(function (w) { return w.ward; }),
        datasets: [{
          label: "Total Investment (₹ Cr)",
          data: wards.map(function (w) { return w.amount_cr; }),
          backgroundColor: COLORS.amber,
          borderRadius: 6
        }]
      },
      options: Object.assign({}, CHART_DEFAULTS, {
        indexAxis: "y",
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { display: false } }),
        scales: {
          x: Object.assign({}, CHART_DEFAULTS.scales.x, { ticks: { color: "#94a3b8", callback: function (v) { return "₹" + v + " Cr"; } } }),
          y: Object.assign({}, CHART_DEFAULTS.scales.y)
        }
      })
    });
  }

  function renderClusterCompareChart(d) {
    var canvas = $("construction-cluster-chart");
    if (!canvas || typeof Chart === "undefined") return;
    var clusters = (d.clustering && d.clustering.clusters) || [];
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: clusters.map(function (c, i) { return "Cluster " + i + " — " + c.label.split(" / ")[0]; }),
        datasets: [
          { label: "Avg Work Orders / Ward", data: clusters.map(function (c) { return c.avg_orders; }), backgroundColor: COLORS.cyan, borderRadius: 6 },
          { label: "Avg Contractors / Ward", data: clusters.map(function (c) { return c.avg_contractors; }), backgroundColor: COLORS.purple, borderRadius: 6 }
        ]
      },
      options: Object.assign({}, CHART_DEFAULTS, {
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { position: "bottom", labels: { color: "#e2e8f0", font: { size: 11 } } } })
      })
    });
  }

  function renderCategoryChart(d) {
    var canvas = $("construction-category-chart");
    if (!canvas || typeof Chart === "undefined") return;
    var tags = d.category_tags || [];
    new Chart(canvas, {
      type: "bar",
      data: {
        labels: tags.map(function (t) { return t.category; }),
        datasets: [{
          label: "Work Orders Tagged",
          data: tags.map(function (t) { return t.count; }),
          backgroundColor: [COLORS.amber, COLORS.cyan, COLORS.emerald, COLORS.rose, COLORS.indigo],
          borderRadius: 6
        }]
      },
      options: Object.assign({}, CHART_DEFAULTS, {
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, { legend: { display: false } })
      })
    });
  }

  function renderTopWardsTable(d) {
    var tbody = $("construction-data-table-body");
    if (!tbody) return;
    var wards = d.top_wards || [];
    tbody.innerHTML = wards.map(function (w) {
      var clusterColor = w.cluster === "High" ? COLORS.amber : COLORS.cyan;
      return "<tr>" +
        "<td><strong>" + w.ward + "</strong></td>" +
        "<td><span style='color:" + clusterColor + ";font-weight:600'>" + w.cluster + "</span></td>" +
        "<td>" + (w.orders || "—") + "</td>" +
        "<td>" + fmtCr(w.amount_cr) + "</td>" +
        "<td>" + fmtCr(w.net_cr) + "</td>" +
        "<td>" + (w.contractors || "—") + "</td>" +
        "</tr>";
    }).join("") || "<tr><td colspan='6'>No data available.</td></tr>";
  }

  function init(data) {
    try { renderOverviewKPIs(data); }      catch(e) { console.error("[Construction] KPIs:", e); }
    try { renderBudgetDonut(data); }       catch(e) { console.error("[Construction] Budget donut:", e); }
    try { renderClusterDonut(data); }      catch(e) { console.error("[Construction] Cluster donut:", e); }
    try { renderTopOrdersChart(data); }    catch(e) { console.error("[Construction] Top orders:", e); }
    try { renderWardHistogram(data); }     catch(e) { console.error("[Construction] Histogram:", e); }
    try { renderInvestmentChart(data); }   catch(e) { console.error("[Construction] Investment:", e); }
    try { renderClusterCompareChart(data); } catch(e) { console.error("[Construction] Cluster compare:", e); }
    try { renderCategoryChart(data); }     catch(e) { console.error("[Construction] Categories:", e); }
    try { renderTopWardsTable(data); }     catch(e) { console.error("[Construction] Table:", e); }
  }

  window.initUrbanPulseConstructionAnalytics = function () {
    var ready = window.URBANPULSE_CONSTRUCTION_READY;
    if (ready && typeof ready.then === "function") {
      ready.then(init).catch(function (e) { console.error("[Construction] Data load failed:", e); });
    } else {
      init(window.URBANPULSE_CONSTRUCTION_DATA || window.UP_CONSTRUCTION || {});
    }
  };

})();
