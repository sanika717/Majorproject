/**
 * UrbanPulse - Analytics page extras (Phase 4B)
 * Tabs + additional charts. Reads ONLY existing verified datasets:
 *   URBANPULSE_CONSTRUCTION_DATA, URBANPULSE_DATA, URBANPULSE_LOCATIONS.
 * Nothing is invented; missing data renders as "Data Not Available".
 */
document.addEventListener("DOMContentLoaded", () => {
  const NA = "Data Not Available";
  const PALETTE = ["#38bdf8", "#f59e0b", "#10b981", "#a855f7", "#f43f5e", "#6366f1", "#14b8a6", "#eab308", "#94a3b8"];
  const $ = (id) => document.getElementById(id);
  const setText = (id, v) => { const el = $(id); if (el) el.textContent = v; };
  const cr = (n) => `₹${(n / 1e7).toFixed(2)} Cr`;

  // ---------- Tabs ----------
  const tabs = document.querySelectorAll(".analytics-tabs [data-tab]");
  function showTab(name) {
    if (!$("tab-" + name)) name = "construction";
    document.querySelectorAll(".analytics-tab-panel").forEach(p => p.classList.toggle("active", p.id === "tab-" + name));
    tabs.forEach(t => t.classList.toggle("active", t.dataset.tab === name));
    if (history.replaceState) history.replaceState(null, "", "#" + name);
    if (window.Chart) Object.values(Chart.instances).forEach(c => c.resize());
  }
  tabs.forEach(t => t.addEventListener("click", () => showTab(t.dataset.tab)));
  showTab((location.hash || "").replace("#", "") || "construction");

  // ---------- Chart helpers ----------
  const tick = "#94a3b8";
  const tooltip = { backgroundColor: "rgba(15,23,42,0.95)", titleColor: "#fff", bodyColor: tick, borderColor: "rgba(56,189,248,0.3)", borderWidth: 1 };
  const axes = { x: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: tick } }, y: { grid: { color: "rgba(255,255,255,0.05)" }, ticks: { color: tick }, beginAtZero: true } };
  const legend = { labels: { color: tick, font: { family: "Inter", size: 12 } } };
  function chart(id, type, labels, datasets, extra = {}) {
    const c = $(id);
    if (!c || !window.Chart) return;
    const donut = type === "doughnut";
    new Chart(c.getContext("2d"), {
      type, data: { labels, datasets },
      options: Object.assign({ responsive: true, maintainAspectRatio: false, plugins: { legend: donut ? { position: "right", ...legend } : legend, tooltip }, scales: donut ? {} : axes }, extra)
    });
  }
  const donutDs = (data) => [{ data, backgroundColor: PALETTE.slice(0, data.length).map(c => c + "cc"), borderColor: "#0a0e17", borderWidth: 2 }];
  const showNA = (canvasId, msg = NA) => {
    const c = $(canvasId); if (!c) return;
    c.parentElement.innerHTML = `<div class="empty-state">${msg}</div>`;
  };

  // ---------- Construction extras ----------
  const cons = window.URBANPULSE_CONSTRUCTION_DATA;
  if (cons && cons.overview) {
    const ov = cons.overview;
    setText("cx-kpi-net", cr(ov.total_net_expenditure));
    setText("cx-kpi-ded", cr(ov.total_deduction));
    setText("cx-kpi-avg", `₹${(ov.total_amount / ov.total_work_orders / 1e5).toFixed(2)} L`);
    chart("cx-budget-donut", "doughnut", ["Net Expenditure", "Deductions"], donutDs([ov.total_net_expenditure, ov.total_deduction]));
    const cl = cons.clustering.clusters;
    chart("cx-cluster-donut", "doughnut", cl.map(c => c.cluster_name), donutDs(cl.map(c => c.ward_count)));
    const top = (cons.top_wards_by_work_orders || []).slice(0, 10);
    if (top.length) {
      chart("cx-top-orders", "bar", top.map(w => `Ward ${w.ward}`),
        [{ label: "Work Orders", data: top.map(w => w.total_work_orders), backgroundColor: "rgba(56,189,248,0.6)", borderColor: "#38bdf8", borderWidth: 1, borderRadius: 6 }]);
    } else showNA("cx-top-orders");
    const wd = cons.ward_level_data || [];
    if (wd.length) {
      const bins = [[0, 10], [11, 20], [21, 30], [31, 40], [41, 50], [51, Infinity]];
      const counts = bins.map(([a, b]) => wd.filter(w => w.total_work_orders >= a && w.total_work_orders <= b).length);
      chart("cx-ward-hist", "bar", bins.map(([a, b]) => b === Infinity ? `${a}+` : `${a}–${b}`),
        [{ label: "Number of Ward Codes", data: counts, backgroundColor: "rgba(16,185,129,0.6)", borderColor: "#10b981", borderWidth: 1, borderRadius: 6 }]);
    } else showNA("cx-ward-hist");
  } else {
    ["cx-budget-donut", "cx-cluster-donut", "cx-top-orders", "cx-ward-hist"].forEach(id => showNA(id));
  }

  // ---------- Crime extras ----------
  const D = window.URBANPULSE_DATA;
  const YEARS = ["2021", "2022", "2023"];
  const yr = (cat, y) => D && D.categories && D.categories[cat] && D.categories[cat].years && D.categories[cat].years[y];
  const sum = (arr, k) => arr.reduce((a, r) => a + (r[k] || 0), 0);
  // Verified per-year totals, taken from the stored total or summed from verified rows.
  const totals = {
    women: y => yr("women", y) ? yr("women", y).total_reported : null,
    children: y => yr("children", y) ? yr("children", y).total_reported : null,
    cyber: y => yr("cyber", y) ? yr("cyber", y).total_reported : null,
    suicides: y => yr("suicides", y) ? (yr("suicides", y).total_suicides ?? sum(yr("suicides", y).items, "total")) : null,
    accidental: y => yr("accidental", y) ? yr("accidental", y).total_accidental_deaths : null
  };
  const series = (key) => YEARS.map(y => totals[key](y));
  if (D) {
    const line = (label, key, color) => ({ label, data: series(key), borderColor: color, backgroundColor: color + "55", tension: 0.3, pointRadius: 5, spanGaps: false });
    chart("cx-crime-cases-line", "line", YEARS, [
      line("Women", "women", "#f43f5e"), line("Children", "children", "#f59e0b"), line("Cyber Crime", "cyber", "#38bdf8")]);
    chart("cx-crime-deaths-bar", "bar", YEARS, [
      { label: "Suicides", data: series("suicides"), backgroundColor: "rgba(168,85,247,0.6)", borderRadius: 6 },
      { label: "Accidental Deaths", data: series("accidental"), backgroundColor: "rgba(245,158,11,0.6)", borderRadius: 6 }]);
    const h = D.historical;
    if (h) chart("cx-crime-fatal-donut", "doughnut", ["Fatal", "Non-Fatal"], donutDs([h.fatal_crimes, h.non_fatal_crimes]));
    else showNA("cx-crime-fatal-donut");
    const cy = yr("cyber", "2023");
    if (cy) chart("cx-crime-cyber-donut", "doughnut", cy.items.map(i => i.division), donutDs(cy.items.map(i => i.reported)));
    else showNA("cx-crime-cyber-donut");

    const rows = [["Crimes Against Women", "women", "Reported cases"], ["Crimes Against Children", "children", "Reported cases"],
      ["Cyber Crime", "cyber", "Reported cases"], ["Suicides", "suicides", "Deaths"], ["Accidental Deaths", "accidental", "Deaths"]];
    const body = $("cx-crime-year-table");
    if (body) body.innerHTML = rows.map(([name, key, unit]) =>
      `<tr><td style="font-weight:700;color:#fff;">${name}</td>${YEARS.map(y => { const v = totals[key](y); return `<td>${v == null ? NA : Number(v).toLocaleString()}</td>`; }).join("")}<td>${unit}</td></tr>`).join("");
  } else {
    ["cx-crime-cases-line", "cx-crime-deaths-bar", "cx-crime-fatal-donut", "cx-crime-cyber-donut"].forEach(id => showNA(id));
  }

  // ---------- Police ----------
  const locs = window.URBANPULSE_LOCATIONS;
  if (Array.isArray(locs) && locs.length) {
    const by = {};
    locs.forEach(l => { (by[l.category] = by[l.category] || { n: 0, src: l.source }).n++; });
    const cats = Object.keys(by);
    const kpi = $("cx-police-kpis");
    if (kpi) kpi.innerHTML = `<div class="kpi-card glass-panel"><div class="kpi-header"><span class="kpi-title">Mapped Locations</span><div class="kpi-icon">📍</div></div><div class="kpi-value">${locs.length}</div><div class="kpi-subtext"><span>Verified KML coordinates</span></div></div>` +
      cats.map(c => `<div class="kpi-card glass-panel"><div class="kpi-header"><span class="kpi-title">${c}</span><div class="kpi-icon">🚓</div></div><div class="kpi-value" style="color: var(--accent-cyan);">${by[c].n}</div><div class="kpi-subtext"><span>Locations</span></div></div>`).join("");
    chart("cx-police-donut", "doughnut", cats, donutDs(cats.map(c => by[c].n)));
    const tb = $("cx-police-table");
    if (tb) tb.innerHTML = cats.map(c => `<tr><td style="font-weight:700;color:#fff;">${c}</td><td>${by[c].n}</td><td style="font-size:11px;">${by[c].src}</td></tr>`).join("");
  } else {
    showNA("cx-police-donut");
  }
});
