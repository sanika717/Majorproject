/**
 * UrbanPulse - Unified Smart City Map Component
 * Handles layer switching, 150 real police locations, popups, and city-level metrics
 */

class SmartCityMap {
  constructor(containerId = "urbanpulse-map") {
    this.containerId = containerId;
    this.map = null;
    this.markersLayer = null;
    this.currentLayer = "construction";
    this.locations = window.URBANPULSE_LOCATIONS || [];
    this.crimeData = window.URBANPULSE_DATA || {};
    this.constructionData = window.URBANPULSE_CONSTRUCTION_DATA || null;
    
    this.initMap();
    this.initEventListeners();
    this.renderLayer(this.currentLayer);
  }

  initMap() {
    // Center on Bengaluru
    this.map = L.map(this.containerId, {
      center: [12.9716, 77.5946],
      zoom: 11,
      minZoom: 9,
      maxZoom: 18,
      zoomControl: true
    });

    // OpenStreetMap standard tiles - no API key required.
    // The dark look is applied purely with a CSS filter on .leaflet-tile-pane (see style.css).
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution: "&copy; OpenStreetMap contributors",
      maxZoom: 19
    }).addTo(this.map);

    this.markersLayer = L.layerGroup().addTo(this.map);
  }

  initEventListeners() {
    const layerSelect = document.getElementById("map-layer-selector");
    if (layerSelect) {
      layerSelect.addEventListener("change", (e) => {
        this.setLayer(e.target.value);
      });
    }

  }

  setLayer(layerId) {
    this.currentLayer = layerId;
    this.renderLayer(layerId);
    
    // Dispatch event for other dashboard components
    window.dispatchEvent(new CustomEvent("urbanpulse:layerChanged", { detail: { layer: layerId } }));
  }

  renderLayer(layerId) {
    const placeholderEl = document.getElementById("map-placeholder-overlay");
    const floatingPanel = document.getElementById("map-floating-panel");
    const constructionPanel = document.getElementById("map-floating-panel-construction");
    const policePanel = document.getElementById("map-floating-panel-police");
    const placeholderTitle = document.getElementById("placeholder-layer-title");
    const placeholderDesc = document.getElementById("placeholder-layer-desc");

    // Clear existing markers
    this.markersLayer.clearLayers();

    this.updateHeaderBar(layerId);

    // Hide both floating panels by default; each branch below turns on the one it needs
    if (floatingPanel) floatingPanel.style.display = "none";
    if (constructionPanel) constructionPanel.style.display = "none";
    if (policePanel) policePanel.style.display = "none";

    if (layerId === "crime") {
      // Crime statistics are city/division-level, so there is nothing real to pin
      // per location: show the live base map + city-level overview panel only.
      if (placeholderEl) placeholderEl.classList.remove("show");
      if (floatingPanel) floatingPanel.style.display = "block";

      this.updateMapStats();
    } else if (layerId === "police") {
      // 150 verified KML station coordinates. No crime totals are attached to them.
      if (placeholderEl) placeholderEl.classList.remove("show");
      if (policePanel) policePanel.style.display = "block";

      this.renderPoliceMarkers();
      this.updatePolicePanel();
    } else if (layerId === "construction" && this.constructionData) {
      // EDA is complete and verified, but no ward-boundary/centroid coordinate
      // dataset was supplied, so there is nothing real to plot as map markers or
      // polygons yet. Rather than hiding this behind the generic "Coming Soon"
      // placeholder (which would understate how much real analysis exists), show
      // the live base map plus a floating KPI panel, and point people at the
      // Analytics page for the real charts/tables.
      if (placeholderEl) placeholderEl.classList.remove("show");
      if (constructionPanel) constructionPanel.style.display = "block";

      this.updateConstructionPanel();
    } else {
      // Layers without a real dataset - strictly no fake data
      const layerMeta = (this.crimeData.map_layers || []).find(l => l.id === layerId) || { name: layerId };

      if (placeholderTitle) placeholderTitle.textContent = "Data Coming Soon";
      if (placeholderDesc) {
        placeholderDesc.textContent = `${layerMeta.name}: no verified dataset has been supplied for this layer yet. Real markers will appear here once data is available.`;
      }
      if (placeholderEl) placeholderEl.classList.add("show");
    }
  }

  // Map header text follows the active layer so it never claims a data source
  // or coordinate count that does not belong to that layer.
  updateHeaderBar(layerId) {
    const titleEl = document.getElementById("map-header-title");
    const sourceEl = document.getElementById("map-header-source");
    if (!titleEl || !sourceEl) return;

    const base = "Bengaluru Metropolitan Area";
    let title = base;
    let source = "Source: no verified dataset supplied yet";

    if (layerId === "construction" && this.constructionData) {
      title = `${base} (ward-level overview — no ward coordinates supplied)`;
      source = "Source: BBMP 2025-26 ward work orders";
    } else if (layerId === "crime") {
      title = `${base} (city-level statistics — no pins)`;
      source = "Source: D47 city-level crime statistics";
    } else if (layerId === "police") {
      title = `${base} (${this.locations.length} verified coordinates)`;
      source = "Source: Karnataka Police GIS KML Datasets";
    }

    titleEl.textContent = title;
    sourceEl.textContent = source;
  }

  updateConstructionPanel() {
    const cd = this.constructionData;
    if (!cd) return;
    const ov = cd.overview;

    const set = (id, val) => {
      const el = document.getElementById(id);
      if (el) el.textContent = val;
    };

    set("construction-panel-orders", ov.total_work_orders.toLocaleString());
    set("construction-panel-amount", `₹${(ov.total_amount / 1e7).toFixed(2)} Cr`);
    set("construction-panel-wards", `${ov.official_numbered_wards_present} / ${ov.official_wards_total}`);
    set("construction-panel-contractors", ov.unique_contractors.toLocaleString());

    const clusters = cd.clustering.clusters;
    const high = clusters.find(c => c.cluster === 0);
    const low = clusters.find(c => c.cluster === 1);
    set("construction-panel-clusters", high && low ? `${high.ward_count} High / ${low.ward_count} Low` : "—");
  }

  renderPoliceMarkers() {
    this.markersLayer.clearLayers();

    // Station popups show ONLY what the KML source provides (name, category,
    // coordinates). City/division-level crime totals are deliberately NOT
    // attached to individual stations: no station-level crime data exists.
    const esc = (t) => String(t).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

    this.locations.forEach((loc, index) => {
      let pinClass = "pin-police";
      let iconSymbol = "🚓";

      if (loc.category === "Railway Police Station") {
        pinClass = "pin-railway";
        iconSymbol = "🚆";
      } else if (loc.category === "Police Outpost") {
        pinClass = "pin-outpost";
        iconSymbol = "🛡️";
      }

      const customIcon = L.divIcon({
        className: "custom-pin-wrapper",
        html: `<div class="custom-pin ${pinClass}" style="width: 28px; height: 28px; font-size: 13px;">${iconSymbol}</div>`,
        iconSize: [28, 28],
        iconAnchor: [14, 14],
        popupAnchor: [0, -14]
      });

      const popupHtml = `
        <div class="popup-inner">
          <h4>${iconSymbol} ${esc(loc.name || loc.category)}</h4>
          <div style="font-size: 12px; color: #cbd5e1; margin-bottom: 4px;">${esc(loc.category)}</div>
          <div style="font-size: 11px; color: #94a3b8; margin-bottom: 6px;">
            Coordinates: ${loc.lat.toFixed(5)}, ${loc.lng.toFixed(5)}
          </div>
          <div class="popup-divider"></div>
          <div class="popup-disclaimer">
            ℹ️ Location from the Karnataka Police GIS KML source. Station-level crime figures are not available, so none are shown. City-level crime statistics are on the Crime & Safety layer.
          </div>
        </div>
      `;

      const marker = L.marker([loc.lat, loc.lng], { icon: customIcon });
      marker.bindPopup(popupHtml, { maxWidth: 300 });
      this.markersLayer.addLayer(marker);
    });
  }

  updatePolicePanel() {
    const counts = {};
    this.locations.forEach(l => { counts[l.category] = (counts[l.category] || 0) + 1; });
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    set("police-panel-total", this.locations.length);
    set("police-panel-stations", counts["Police Station"] || 0);
    set("police-panel-outposts", counts["Police Outpost"] || 0);
    set("police-panel-railway", counts["Railway Police Station"] || 0);
  }

  updateMapStats() {
    const hist = this.crimeData.historical || null;

    const yearEl = document.getElementById("floating-stat-year");
    const totalEl = document.getElementById("floating-stat-total");
    const fatalEl = document.getElementById("floating-stat-fatal");
    const nonFatalEl = document.getElementById("floating-stat-nonfatal");
    const fatalPctEl = document.getElementById("floating-stat-fatalpct");
    const riskBadgeEl = document.getElementById("floating-stat-risk");
    const locCountEl = document.getElementById("floating-stat-loccount");

    if (locCountEl) locCountEl.textContent = this.locations.length;

    if (!hist) {
      if (yearEl) yearEl.textContent = "N/A";
      if (totalEl) totalEl.textContent = "—";
      if (fatalEl) fatalEl.textContent = "—";
      if (nonFatalEl) nonFatalEl.textContent = "—";
      if (fatalPctEl) fatalPctEl.textContent = "—";
      if (riskBadgeEl) riskBadgeEl.textContent = "Data Unavailable";
      return;
    }

    if (yearEl) yearEl.textContent = hist.period_label;
    if (totalEl) totalEl.textContent = hist.total_crimes.toLocaleString();
    if (fatalEl) fatalEl.textContent = hist.fatal_crimes.toLocaleString();
    if (nonFatalEl) nonFatalEl.textContent = hist.non_fatal_crimes.toLocaleString();
    if (fatalPctEl) fatalPctEl.textContent = `${hist.fatal_percentage}%`;

    if (riskBadgeEl) {
      riskBadgeEl.textContent = `${hist.highest_risk_level} (peak ${hist.highest_risk_year})`;
      riskBadgeEl.style.color = hist.highest_risk_level === "High Risk" ? "#ef4444" : "#f59e0b";
      riskBadgeEl.style.background = hist.highest_risk_level === "High Risk" ? "rgba(239, 68, 68, 0.15)" : "rgba(245, 158, 11, 0.15)";
    }
  }
}

// Global initialization helper
window.initUrbanPulseMap = function() {
  window.urbanpulseMapInstance = new SmartCityMap("urbanpulse-map");
};
