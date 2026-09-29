/**
 * UrbanPulse - Dashboard headline KPIs
 * Reads ONLY already-verified datasets (construction EDA export, D47 crime
 * historical total, KML police locations). Nothing is computed or invented here.
 */
document.addEventListener("DOMContentLoaded", () => {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

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
});
