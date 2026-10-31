/**
 * UrbanPulse - Dashboard Map Panel
 * Patches the construction map floating panel with verified overview figures
 * (work orders, total investment in Cr, ward coverage, contractors, and clusters).
 */
document.addEventListener("DOMContentLoaded", () => {
  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };

  const cons = window.URBANPULSE_CONSTRUCTION_DATA || (window.UP_CONSTRUCTION || {});
  const ov = cons.overview || {};

  // ── Patch construction map floating panel ──────────────────────────────────
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
