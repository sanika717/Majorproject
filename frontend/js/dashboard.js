/**
 * UrbanPulse - Dashboard headline KPIs
 * Fetches verified headline figures from the FastAPI backend + PostgreSQL database
 * (Construction work orders & investment, D47 crime totals, KML police locations).
 */
document.addEventListener("DOMContentLoaded", async () => {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  // 1. Initial display from cache/globals if available
  const cons = window.URBANPULSE_CONSTRUCTION_DATA;
  if (cons && cons.overview) {
    set("dash-kpi-orders", cons.overview.total_work_orders.toLocaleString());
    set("dash-kpi-amount", `₹${(cons.overview.total_amount / 1e7).toFixed(2)} Cr`);
  }

  const hist = window.URBANPULSE_DATA && window.URBANPULSE_DATA.historical;
  if (hist) {
    set("dash-kpi-crimes", hist.total_crimes.toLocaleString());
    if (hist.period_label) set("dash-kpi-crimes-period", `D47 city-level total, ${hist.period_label}`);
  }

  const locs = window.URBANPULSE_LOCATIONS;
  if (Array.isArray(locs)) set("dash-kpi-police", locs.length.toLocaleString());

  // 2. Fetch fresh headline figures from FastAPI backend
  if (window.UrbanPulseAPI) {
    try {
      const data = await window.UrbanPulseAPI.getDashboardKPIs();
      if (data && data.kpis) {
        const k = data.kpis;
        set("dash-kpi-orders", k.total_work_orders.toLocaleString());
        set("dash-kpi-amount", k.total_construction_investment_formatted || `₹${(k.total_construction_investment / 1e7).toFixed(2)} Cr`);
        set("dash-kpi-crimes", k.total_recorded_crimes.toLocaleString());
        if (k.crimes_period_label) set("dash-kpi-crimes-period", k.crimes_period_label);
        set("dash-kpi-police", k.mapped_police_locations.toLocaleString());
      }
    } catch (e) {
      console.warn("[Dashboard] Could not fetch live KPIs from backend API:", e);
    }
  }
});
