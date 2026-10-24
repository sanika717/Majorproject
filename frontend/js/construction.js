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

  function makeChart(canvas, config) {
    if (!canvas || typeof Chart === "undefined") return null;
    var existing = Chart.getChart(canvas);
    if (existing) {
      existing.destroy();
    }
    return new Chart(canvas, config);
  }

  function renderOverviewKPIs(d) {
    var o = d.overview || {};
    var el;
    el = $("cx-kpi-net");   if (el) el.textContent = fmtCr(o.net_expenditure_cr);
    el = $("cx-kpi-ded");   if (el) el.textContent = fmtCr(o.total_deductions_cr);
    el = $("cx-kpi-avg");   if (el) el.textContent = o.avg_amount_per_order_lakh ? "₹" + fmt(o.avg_amount_per_order_lakh, 2) + " L" : "—";

    el = $("construction-kpi-orders");      if (el && o.total_work_orders) el.textContent = Number(o.total_work_orders).toLocaleString("en-IN");
    el = $("construction-kpi-amount") || $("construction-kpi-investment");
    if (el && o.total_amount_cr != null) el.textContent = fmtCr(o.total_amount_cr);
    
    el = $("construction-kpi-wards") || $("construction-kpi-coverage");
    if (el && o.ward_coverage != null) el.textContent = o.ward_coverage + " / " + (o.total_wards || 198);

    el = $("construction-kpi-contractors"); if (el && o.unique_contractors) el.textContent = Number(o.unique_contractors).toLocaleString("en-IN");
    el = $("construction-kpi-deduction");   if (el && o.avg_deduction_rate_pct != null) el.textContent = fmt(o.avg_deduction_rate_pct, 2) + "%";
    el = $("construction-kpi-nonstandard"); if (el && o.non_standard_ward_codes != null) el.textContent = o.non_standard_ward_codes;

    // Update Cluster KPI Box stats
    var clusters = (d.clustering && d.clustering.clusters) || [];
    var high = clusters.find(function(c) { return String(c.label).indexOf("High") >= 0; }) || clusters[0];
    var low  = clusters.find(function(c) { return String(c.label).indexOf("Low") >= 0; }) || clusters[1];
    if (high) {
      el = $("cluster-high-count");       if (el) el.textContent = high.wards != null ? high.wards : "—";
      el = $("cluster-high-orders");      if (el) el.textContent = fmt(high.avg_orders, 1);
      el = $("cluster-high-amount");      if (el) el.textContent = fmtCr(high.avg_amount_cr);
      el = $("cluster-high-contractors"); if (el) el.textContent = fmt(high.avg_contractors, 1);
    }
    if (low) {
      el = $("cluster-low-count");        if (el) el.textContent = low.wards != null ? low.wards : "—";
      el = $("cluster-low-orders");      if (el) el.textContent = fmt(low.avg_orders, 1);
      el = $("cluster-low-amount");      if (el) el.textContent = fmtCr(low.avg_amount_cr);
      el = $("cluster-low-contractors"); if (el) el.textContent = fmt(low.avg_contractors, 1);
    }
    el = $("cluster-silhouette"); if (el && d.clustering && d.clustering.silhouette_score != null) {
      el.textContent = fmt(d.clustering.silhouette_score, 4);
    }
  }

  function renderBudgetDonut(d) {
    var canvas = $("cx-budget-donut");
    if (!canvas) return;
    var o = d.overview || {};
    var net = o.net_expenditure_cr != null ? o.net_expenditure_cr : 2857.58;
    var ded = o.total_deductions_cr != null ? o.total_deductions_cr : 311.48;
    makeChart(canvas, {
      type: "doughnut",
      data: {
        labels: ["Net Expenditure", "Deductions"],
        datasets: [{
          data: [net, ded],
          backgroundColor: [COLORS.emerald, COLORS.rose],
          borderColor: "#0a0e17",
          borderWidth: 3,
          hoverOffset: 10
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: "65%",
        plugins: {
          legend: { position: "bottom", labels: { color: "#e2e8f0", font: { size: 12 } } },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ctx.label + ": ₹" + ctx.parsed.toFixed(2) + " Cr";
              }
            }
          }
        }
      }
    });
  }

  function renderClusterDonut(d) {
    var canvas = $("cx-cluster-donut");
    if (!canvas) return;
    var clusters = (d.clustering && d.clustering.clusters) || [];
    if (!clusters.length) return;
    makeChart(canvas, {
      type: "doughnut",
      data: {
        labels: clusters.map(function (c) { return String(c.label || "Cluster").split(" / ")[0]; }),
        datasets: [{
          data: clusters.map(function (c) { return c.wards || 0; }),
          backgroundColor: [COLORS.amber, COLORS.cyan],
          borderColor: "#0a0e17",
          borderWidth: 3,
          hoverOffset: 10
        }]
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: "65%",
        plugins: {
          legend: { position: "bottom", labels: { color: "#e2e8f0", font: { size: 12 } } },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ctx.label + ": " + ctx.parsed + " wards";
              }
            }
          }
        }
      }
    });
  }

  function renderTopOrdersChart(d) {
    var canvas = $("cx-top-orders");
    if (!canvas) return;
    var wards = (d.top_wards_by_work_orders || d.top_wards || []).slice(0, 10);
    if (!wards.length) {
      if (canvas.parentElement) {
        canvas.parentElement.innerHTML = "<p style='color:var(--text-muted);text-align:center;padding:24px;'>Data unavailable</p>";
      }
      return;
    }
    makeChart(canvas, {
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
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return "Work Orders: " + Number(ctx.parsed.y).toLocaleString("en-IN");
              }
            }
          }
        }),
        scales: Object.assign({}, CHART_DEFAULTS.scales, {
          x: Object.assign({}, CHART_DEFAULTS.scales.x, { ticks: { color: "#94a3b8", maxRotation: 40, font: { size: 10 } } })
        })
      })
    });
  }

  function renderWardHistogram(d) {
    var canvas = $("cx-ward-hist");
    if (!canvas) return;
    var bins = d.ward_histogram || [];
    if (!bins.length) {
      if (canvas.parentElement) {
        canvas.parentElement.innerHTML = "<p style='color:var(--text-muted);text-align:center;padding:24px;'>Data unavailable</p>";
      }
      return;
    }
    makeChart(canvas, {
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
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return "Wards in range: " + ctx.parsed.y;
              }
            }
          }
        })
      })
    });
  }

  function renderInvestmentChart(d) {
    var canvas = $("construction-investment-chart");
    if (!canvas) return;
    var wards = (d.top_wards_by_investment || d.top_wards || []).slice(0, 10);
    if (!wards.length) {
      if (canvas.parentElement) {
        canvas.parentElement.innerHTML = "<p style='color:var(--text-muted);text-align:center;padding:24px;'>Data unavailable</p>";
      }
      return;
    }
    makeChart(canvas, {
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
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return "Total Investment: ₹" + Number(ctx.parsed.x).toFixed(2) + " Cr";
              }
            }
          }
        }),
        scales: {
          x: Object.assign({}, CHART_DEFAULTS.scales.x, { ticks: { color: "#94a3b8", callback: function (v) { return "₹" + v + " Cr"; } } }),
          y: Object.assign({}, CHART_DEFAULTS.scales.y)
        }
      })
    });
  }

  function renderClusterCompareChart(d) {
    var canvas = $("construction-cluster-chart");
    if (!canvas) return;
    var clusters = (d.clustering && d.clustering.clusters) || [];
    if (!clusters.length) return;
    makeChart(canvas, {
      type: "bar",
      data: {
        labels: clusters.map(function (c, i) { return "Cluster " + i + " — " + String(c.label || "Cluster").split(" / ")[0]; }),
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
    if (!canvas) return;
    var tags = d.category_tags || [];
    if (!tags.length) {
      if (canvas.parentElement) {
        canvas.parentElement.innerHTML = "<p style='color:var(--text-muted);text-align:center;padding:24px;'>Data unavailable</p>";
      }
      return;
    }
    makeChart(canvas, {
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
        plugins: Object.assign({}, CHART_DEFAULTS.plugins, {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function (ctx) {
                return ctx.dataset.label + ": " + Number(ctx.parsed.y).toLocaleString("en-IN");
              }
            }
          }
        })
      })
    });
  }

  function renderTopWardsTable(d) {
    var tbody = $("construction-data-table-body");
    if (!tbody) return;
    var wards = d.top_wards_by_investment || d.top_wards || [];
    if (!wards.length) {
      tbody.innerHTML = "<tr><td colspan='6' style='text-align:center;color:var(--text-muted);padding:16px;'>Data unavailable</td></tr>";
      return;
    }
    tbody.innerHTML = wards.map(function (w) {
      var isHigh = String(w.cluster || "").indexOf("High") >= 0;
      var clusterColor = isHigh ? COLORS.amber : COLORS.cyan;
      var clusterText = isHigh ? "High Development" : "Low Development";
      return "<tr>" +
        "<td><strong>" + (w.ward || "Data unavailable") + "</strong></td>" +
        "<td><span style='color:" + clusterColor + ";font-weight:600'>" + clusterText + "</span></td>" +
        "<td>" + (w.orders != null ? Number(w.orders).toLocaleString("en-IN") : "Data unavailable") + "</td>" +
        "<td>" + fmtCr(w.amount_cr) + "</td>" +
        "<td>" + fmtCr(w.net_cr) + "</td>" +
        "<td>" + (w.contractors != null ? Number(w.contractors).toLocaleString("en-IN") : "Data unavailable") + "</td>" +
        "</tr>";
    }).join("");
  }

  function init(data) {
    if (!data) return;
    try { renderOverviewKPIs(data); }        catch(e) { console.error("[Construction] KPIs:", e); }
    try { renderBudgetDonut(data); }         catch(e) { console.error("[Construction] Budget donut:", e); }
    try { renderClusterDonut(data); }        catch(e) { console.error("[Construction] Cluster donut:", e); }
    try { renderTopOrdersChart(data); }      catch(e) { console.error("[Construction] Top orders:", e); }
    try { renderWardHistogram(data); }       catch(e) { console.error("[Construction] Histogram:", e); }
    try { renderInvestmentChart(data); }     catch(e) { console.error("[Construction] Investment:", e); }
    try { renderClusterCompareChart(data); } catch(e) { console.error("[Construction] Cluster compare:", e); }
    try { renderCategoryChart(data); }       catch(e) { console.error("[Construction] Categories:", e); }
    try { renderTopWardsTable(data); }       catch(e) { console.error("[Construction] Table:", e); }
  }

  window.initUrbanPulseConstructionAnalytics = function () {
    var ready = window.URBANPULSE_CONSTRUCTION_READY;
    if (ready && typeof ready.then === "function") {
      ready.then(init).catch(function (e) {
        console.error("[Construction] Data load failed, using fallback:", e);
        init(window.UP_CONSTRUCTION || {});
      });
    } else {
      init(window.URBANPULSE_CONSTRUCTION_DATA || window.UP_CONSTRUCTION || {});
    }
  };

})();
