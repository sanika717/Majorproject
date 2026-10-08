/**
 * UrbanPulse - Dashboard headline KPIs
 * Fetches verified headline figures from the FastAPI backend + PostgreSQL database
 * (Construction work orders & investment, D47 crime totals, KML police locations).
 * Falls back to window.UP_CONSTRUCTION / window.UP_CRIME / window.UP_POLICE
 * from data.js when the backend API is not running.
 */
document.addEventListener("DOMContentLoaded", async () => {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  // ── 1. Pre-fill from static verified globals (data.js) ────────────────────

  // Construction — field is total_amount_cr (already in Crores, no division needed)
  const cons = window.URBANPULSE_CONSTRUCTION_DATA || (window.UP_CONSTRUCTION || {});
  const ov = cons.overview || {};
  if (ov.total_work_orders != null) {
    set("dash-kpi-orders", Number(ov.total_work_orders).toLocaleString("en-IN"));
  }
  if (ov.total_amount_cr != null) {
    // total_amount_cr is already in Crores — just format it
    set("dash-kpi-amount", `₹${Number(ov.total_amount_cr).toFixed(2)} Cr`);
  }

  // Crime — read from UP_CRIME.overall.total (set by data.js)
  const crime = window.UP_CRIME || {};
  const overall = crime.overall || {};
  if (overall.total != null) {
    set("dash-kpi-crimes", Number(overall.total).toLocaleString("en-IN"));
    set("dash-kpi-crimes-period", `D47 city-level total, ${overall.period || "2014–2021"}`);
  }

  // Police — read from UP_POLICE.total (set by data.js)
  const police = window.UP_POLICE || {};
  if (police.total != null) {
    set("dash-kpi-police", Number(police.total).toLocaleString("en-IN"));
  }

  // ── 2. Override with live API values if backend is running ────────────────
  if (window.UrbanPulseAPI) {
    try {
      const data = await window.UrbanPulseAPI.getDashboardKPIs();
      if (data && data.kpis) {
        const k = data.kpis;
        if (k.total_work_orders != null)
          set("dash-kpi-orders", Number(k.total_work_orders).toLocaleString("en-IN"));
        if (k.total_construction_investment_formatted)
          set("dash-kpi-amount", k.total_construction_investment_formatted);
        else if (k.total_construction_investment != null)
          set("dash-kpi-amount", `₹${(Number(k.total_construction_investment) / 1e7).toFixed(2)} Cr`);
        if (k.total_recorded_crimes != null)
          set("dash-kpi-crimes", Number(k.total_recorded_crimes).toLocaleString("en-IN"));
        if (k.crimes_period_label)
          set("dash-kpi-crimes-period", k.crimes_period_label);
        if (k.mapped_police_locations != null)
          set("dash-kpi-police", Number(k.mapped_police_locations).toLocaleString("en-IN"));
      }
    } catch (e) {
      console.warn("[Dashboard] Could not fetch live KPIs from backend API:", e);
    }
  }

  // ── 3. Also patch construction map floating panel from same source ─────────
  const conReady = window.URBANPULSE_CONSTRUCTION_READY;
  const patchPanel = (d) => {
    const o = (d && d.overview) || ov;
    if (o.total_work_orders != null)
      set("construction-panel-orders", Number(o.total_work_orders).toLocaleString("en-IN"));
    if (o.total_amount_cr != null)
      set("construction-panel-amount", `₹${Number(o.total_amount_cr).toFixed(2)} Cr`);
    if (o.ward_coverage != null)
      set("construction-panel-wards", `${o.ward_coverage} / ${o.total_wards || o.ward_coverage}`);
    if (o.unique_contractors != null)
      set("construction-panel-contractors", Number(o.unique_contractors).toLocaleString("en-IN"));
    const k = (d && d.clustering && d.clustering.k) || 2;
    set("construction-panel-clusters", `K=${k} (K-Means++)`);
  };
  if (conReady && typeof conReady.then === "function") {
    conReady.then(patchPanel).catch(() => patchPanel(null));
  } else {
    patchPanel(null);
  }
});
