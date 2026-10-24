/**
 * UrbanPulse - ESG Survey: Area-wise Civic Utility Data & Dataset Registry
 *
 * ZERO fabrication rule: every number comes from a registered, verified dataset.
 * "Data unavailable" is shown — and NO map marker is drawn — when no dataset
 * covers that area or metric.
 *
 * DATA SOURCES:
 *  Water quality  : KSPCB MINARS 2020-21 (water_quality_lakes_2020_21.json)
 *                   Per-area aggregation via district field tag matching.
 *  Electricity    : BESCOM via OpenCity (API /api/v1/esg/electricity)
 *                   City-level ONLY — no area-wise breakdown exists.
 *  Water supply   : No BWSSB area-wise dataset registered -> "Data unavailable".
 *
 * WATER QUALITY CLASSIFICATION (CPCB class points: A=100 B=80 C=60 D=40 E=20):
 *  Mean score >= 70  -> Normal       (predominantly Class A/B)
 *  Mean score 50-69  -> High Concern (predominantly Class C)
 *  Mean score < 50   -> Critical     (predominantly Class D/E)
 *
 * Map markers appear ONLY for areas with confirmed lake/tank station records.
 */
(function () {
  "use strict";

  var WQ_THRESHOLDS = [
    { min: 70, label: "Normal",       color: "#10b981" },
    { min: 50, label: "High Concern", color: "#f59e0b" },
    { min: 0,  label: "Critical",     color: "#f43f5e" }
  ];

  var CLASS_POINTS = { A: 100, B: 80, C: 60, D: 40, E: 20 };

  // Approximate area centroids — same values as esg-areas.js, used for map display.
  // Disclosed: administrative centroids, not surveyed station coordinates.
  var AREAS = [
    { id: "bommanahalli", name: "Bommanahalli",         lat: 12.905, lng: 77.625, tag: "Bommanahalli" },
    { id: "mahadevapura", name: "Mahadevapura",         lat: 12.990, lng: 77.700, tag: "Mahadevapura" },
    { id: "dasarahalli",  name: "Dasarahalli",          lat: 13.045, lng: 77.500, tag: "Dasarahalli" },
    { id: "yelahanka",    name: "Yelahanka",            lat: 13.100, lng: 77.590, tag: "Yelahanka" },
    { id: "rrnagar",      name: "Rajarajeshwari Nagar", lat: 12.930, lng: 77.500, tag: "Rajarajeswarinagara" },
    { id: "south",        name: "Bengaluru South",      lat: 12.930, lng: 77.580, tag: "BNG-City South" },
    { id: "east",         name: "Bengaluru East",       lat: 12.980, lng: 77.630, tag: "BNG-City East" },
    { id: "west",         name: "Bengaluru West",       lat: 12.990, lng: 77.540, tag: "BNG-City - West" },
    { id: "peenya",       name: "Peenya",               lat: 13.030, lng: 77.520, tag: "Peenya" },
    { id: "sarjapura",    name: "Sarjapura",            lat: 12.860, lng: 77.780, tag: "Sarjapura" },
    { id: "anekal",       name: "Anekal",               lat: 12.710, lng: 77.690, tag: "Anekal" }
  ];

  var isNum = function (v) { return typeof v === "number" && isFinite(v); };
  var mean  = function (a) { return a.length ? a.reduce(function (s, v) { return s + v; }, 0) / a.length : null; };
  var $     = function (id) { return document.getElementById(id); };
  var esc   = function (s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  };

  function classify(score) {
    if (!isNum(score)) return null;
    for (var i = 0; i < WQ_THRESHOLDS.length; i++) {
      if (score >= WQ_THRESHOLDS[i].min) return WQ_THRESHOLDS[i];
    }
    return WQ_THRESHOLDS[WQ_THRESHOLDS.length - 1];
  }

  function waterByArea(water) {
    var result = {};
    AREAS.forEach(function (area) {
      var pts = [], satisfactory = 0, stationCount = 0, stationNames = [], classDist = {};
      (water.stations || []).forEach(function (st) {
        var m = /\(([^)]+)\)/.exec(st.district || "");
        if (!m || m[1].trim() !== area.tag) return;
        var counted = false;
        (st.months || []).forEach(function (mo) {
          var cls = mo["class"];
          if (!cls || !isNum(CLASS_POINTS[cls])) return;
          pts.push(CLASS_POINTS[cls]);
          classDist[cls] = (classDist[cls] || 0) + 1;
          if (mo.wqi === "S") satisfactory++;
          counted = true;
        });
        if (counted) { stationCount++; stationNames.push(st.name); }
      });
      result[area.id] = {
        area: area, score: mean(pts), stationMonths: pts.length,
        stations: stationCount, stationNames: stationNames, classDist: classDist,
        pctSatisfactory: pts.length ? Math.round(100 * satisfactory / pts.length) : null,
        hasData: stationCount > 0
      };
    });
    return result;
  }

  function renderWaterMap(wqData) {
    var mapEl = $("esg-survey-wq-map");
    if (!mapEl || typeof L === "undefined" || mapEl._leaflet_id) return;

    var map = L.map("esg-survey-wq-map").setView([12.96, 77.59], 10);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: "&copy; <a href='https://www.openstreetmap.org/copyright'>OpenStreetMap</a> contributors"
    }).addTo(map);

    var legend = L.control({ position: "bottomright" });
    legend.onAdd = function () {
      var div = L.DomUtil.create("div", "");
      div.style.cssText = "background:rgba(10,14,23,0.9);padding:8px 12px;border-radius:8px;border:1px solid rgba(255,255,255,0.1);font-size:11px;color:#e2e8f0;line-height:1.9;min-width:170px";
      div.innerHTML = "<strong style='font-size:11px;display:block;margin-bottom:4px'>Water Quality (KSPCB MINARS)</strong>" +
        WQ_THRESHOLDS.map(function (t) {
          return "<span style='display:inline-block;width:10px;height:10px;border-radius:2px;background:" + t.color + ";margin-right:5px;vertical-align:middle'></span>" + t.label;
        }).join("<br>") +
        "<br><span style='color:#64748b;font-size:10px'>Score = mean CPCB class points</span>";
      return div;
    };
    legend.addTo(map);

    var hasMarker = false;
    AREAS.forEach(function (area) {
      var d = wqData[area.id];
      if (!d || !d.hasData) return;
      hasMarker = true;

      var cls = classify(d.score);
      var color = cls ? cls.color : "#94a3b8";
      var distStr = Object.keys(d.classDist).sort().map(function (c) {
        return "Class " + c + ": " + d.classDist[c];
      }).join(", ");

      var popupHtml = "<div style='font-family:Inter,sans-serif;min-width:220px'>" +
        "<strong style='font-size:14px;color:#e2e8f0'>" + esc(area.name) + "</strong><br>" +
        "<span style='font-size:12px;color:" + color + ";font-weight:700'>" + (cls ? cls.label : "n/a") + "</span>" +
        " <span style='font-size:11px;color:#94a3b8'>Score: " + (isNum(d.score) ? d.score.toFixed(1) : "n/a") + " / 100</span><br>" +
        "<hr style='border:none;border-top:1px solid rgba(255,255,255,0.1);margin:6px 0'>" +
        "<div style='font-size:11px;color:#cbd5e1;line-height:1.7'>" +
        "Lakes/tanks monitored: <strong>" + d.stations + "</strong><br>" +
        "Station-months: <strong>" + d.stationMonths + "</strong><br>" +
        "Satisfactory readings: <strong>" + (d.pctSatisfactory !== null ? d.pctSatisfactory + "%" : "n/a") + "</strong><br>" +
        "Class distribution: <strong>" + esc(distStr) + "</strong><br>" +
        "<span style='color:#64748b'>Source: KSPCB MINARS, Apr 2020-Mar 2021<br>" +
        "Centroid: approximate administrative centre</span></div></div>";

      var marker = L.circleMarker([area.lat, area.lng], {
        radius: 16, color: "#0a0e17", weight: 2, fillColor: color, fillOpacity: 0.88
      }).addTo(map);
      marker.bindTooltip(area.name + ": " + (cls ? cls.label : "n/a"), { permanent: false, direction: "top" });
      marker.bindPopup(popupHtml, { maxWidth: 280 });
    });

    if (!hasMarker) {
      mapEl.innerHTML = "<div style='display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-muted);font-size:13px'>No areas with verified lake data found.</div>";
    }
  }

  function renderWaterTable(wqData) {
    var tbody = $("esg-survey-wq-rows");
    if (!tbody) return;
    var html = "";
    AREAS.forEach(function (area) {
      var d = wqData[area.id];
      if (!d || !d.hasData) {
        html += "<tr><td><strong>" + esc(area.name) + "</strong></td>" +
          "<td colspan='4' style='color:var(--text-muted);font-style:italic'>Data unavailable &mdash; no KSPCB lake/tank monitoring stations recorded in this area</td></tr>";
        return;
      }
      var cls = classify(d.score);
      var color = cls ? cls.color : "#94a3b8";
      var badge = cls
        ? "<span style='display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700;border:1px solid " + color + ";color:" + color + "'>" + cls.label + "</span>"
        : "<span style='color:var(--text-muted)'>-</span>";
      var dom = Object.entries(d.classDist).sort(function (a, b) { return b[1] - a[1]; });
      var domStr = dom.slice(0, 2).map(function (e) { return "Class " + e[0] + " (" + e[1] + ")"; }).join(", ");

      html += "<tr><td><strong>" + esc(area.name) + "</strong></td>" +
        "<td><strong style='color:" + color + "'>" + (isNum(d.score) ? d.score.toFixed(1) : "-") + "</strong> / 100</td>" +
        "<td>" + badge + "</td>" +
        "<td style='font-size:11px'>" + d.stations + " lake(s) &middot; " + d.stationMonths + " months<br>" +
        "<span style='color:var(--text-muted)'>" + esc(domStr) + "</span></td>" +
        "<td>" + (d.pctSatisfactory !== null ? "<strong>" + d.pctSatisfactory + "%</strong>" : "-") + "</td></tr>";
    });
    tbody.innerHTML = html || "<tr><td colspan='5'>No data.</td></tr>";
  }

  function renderElecChart(elecData) {
    var wrapper = $("esg-survey-elec-wrapper");
    var loading = $("esg-survey-elec-loading");
    if (!wrapper) return;

    if (!elecData || !elecData.rows || !elecData.rows.length) {
      if (loading) loading.style.display = "none";
      wrapper.innerHTML = "<p style='color:var(--text-muted);padding:20px;text-align:center;font-style:italic'>Electricity data not available from API.</p>";
      return;
    }

    var consumed = elecData.rows.filter(function (r) {
      return r.category && r.category.toLowerCase().indexOf("consumed") >= 0;
    }).sort(function (a, b) { return a.year.localeCompare(b.year); });

    var inputRows = elecData.rows.filter(function (r) {
      return r.category && r.category.toLowerCase().indexOf("energy input") >= 0;
    }).sort(function (a, b) { return a.year.localeCompare(b.year); });

    if (!consumed.length) {
      if (loading) loading.style.display = "none";
      wrapper.innerHTML = "<p style='color:var(--text-muted);padding:20px;text-align:center'>No consumption rows in dataset.</p>";
      return;
    }

    if (loading) loading.style.display = "none";
    var canvas = document.createElement("canvas");
    wrapper.innerHTML = "";
    wrapper.appendChild(canvas);

    var labels = consumed.map(function (r) { return r.year; });
    var consumedVals = consumed.map(function (r) { return +(r.value_lakh_units / 10).toFixed(1); });
    var inputVals = inputRows.map(function (r) { return +(r.value_lakh_units / 10).toFixed(1); });

    new Chart(canvas.getContext("2d"), {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Metered Consumption (MU)",
            data: consumedVals,
            borderColor: "#f59e0b",
            backgroundColor: "rgba(245,158,11,0.08)",
            pointBackgroundColor: "#f59e0b",
            pointRadius: 4, tension: 0.3, fill: true
          },
          {
            label: "Energy Input to Grid (MU)",
            data: inputVals,
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56,189,248,0.04)",
            pointBackgroundColor: "#38bdf8",
            pointRadius: 4, tension: 0.3, fill: false
          }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { labels: { color: "#e2e8f0", font: { size: 12 }, usePointStyle: true } },
          tooltip: { backgroundColor: "rgba(10,14,23,0.9)", titleColor: "#e2e8f0", bodyColor: "#94a3b8" }
        },
        scales: {
          x: { ticks: { color: "#94a3b8", font: { size: 10 } }, grid: { color: "rgba(255,255,255,0.05)" } },
          y: {
            ticks: { color: "#94a3b8" }, grid: { color: "rgba(255,255,255,0.05)" },
            title: { display: true, text: "Million Units (MU)", color: "#94a3b8", font: { size: 11 } }
          }
        }
      }
    });
  }

  function renderDatasetTable(waterData, elecData, airData) {
    var tbody = $("esg-datasets-rows");
    if (!tbody) return;

    var waterSrc = (waterData && waterData.source) || {};
    var elecSrcList = (elecData && elecData.sources) || [];
    var elecSrc = elecSrcList.filter(function (s) { return s.code === "BESCOM_OPENCITY"; })[0] || {};
    var elecOGD = elecSrcList.filter(function (s) { return s.code === "BESCOM_OGD"; })[0] || {};
    var airSrc = (airData && airData.sources) ? airData.sources.filter(function (s) { return s.code === "GUTTIKUNDA_2019"; })[0] || {} : {};

    var REGISTRY = [
      {
        filename: "water_quality_lakes_2020_21.json",
        area: "Bangalore Urban district — " + (waterData && waterData.stations ? waterData.stations.length : 106) + " lake/tank monitoring stations",
        metrics: "Water Quality Class (CPCB A-E) · WQI Status (Satisfactory / Unsatisfactory) · Monthly observations",
        period: waterSrc.period || "Apr 2020 - Mar 2021",
        publisher: waterSrc.publisher || "Karnataka State Pollution Control Board (KSPCB)",
        url: waterSrc.url || "https://karnataka.data.gov.in/resource/water-quality-lakestanks-bangalore-during-2020-2021",
        note: null, available: true
      },
      {
        filename: "BESCOM_OPENCITY (fixture: bescom_consumption.csv)",
        area: "BESCOM supply area — Bengaluru + surrounding districts (NOT area/zone-wise breakdown)",
        metrics: "Electricity consumed, metered categories (lakh units/yr) · Energy input to grid (MU/yr) · Revenue · Consumer count",
        period: elecSrc.period || "2010-11 to 2022-23",
        publisher: elecSrc.publisher || "BESCOM (bescom.karnataka.gov.in), republished by OpenCity.in",
        url: elecSrc.url || "https://data.opencity.in/dataset/bescom-consumption-data",
        note: "City-level only — no area-wise breakdown registered", available: true
      },
      {
        filename: "air_quality_stations.json",
        area: "Greater Bengaluru region — 11 KSPCB manual monitoring stations",
        metrics: "Annual means (ug/m3): PM2.5, PM10, NO2, SO2, NH3, Lead",
        period: "2016-17",
        publisher: airSrc.publisher || "Guttikunda et al. 2019 (Atmospheric Pollution Research), using KSPCB monitoring data",
        url: airSrc.url || "https://urbanemissions.info/wp-content/uploads/docs/2019-01-APR-AQ-Bengaluru.pdf",
        note: null, available: true
      },
      {
        filename: "carbon_emissions.json",
        area: "BBMP administrative area (city-level GHG inventory)",
        metrics: "GHG total (MMt CO2e) · Sector shares (transport, buildings, waste, industry)",
        period: "2019 (base year)",
        publisher: "BBMP Bengaluru Climate Action and Resilience Plan (BCAP), with WRI India / C40",
        url: "https://apps.bbmpgov.in/bcap/PDF/Executive%20summary_English%2018072025.pdf",
        note: null, available: true
      },
      {
        filename: "No registered dataset",
        area: "All Bengaluru areas",
        metrics: "Water supply hours/day, supply timings, BWSSB zone coverage",
        period: "N/A",
        publisher: "No BWSSB area-wise domestic water-supply timing dataset is registered",
        url: null,
        note: "No marker shown; no value displayed anywhere on this page", available: false
      },
      {
        filename: "electricity_consumption.json (empty by design)",
        area: "All Bengaluru areas",
        metrics: "Area-wise electricity availability / zone-level consumption breakdown",
        period: "N/A",
        publisher: "No genuine area-wise electricity dataset retrieved from BESCOM / data.gov.in",
        url: elecOGD.url || "https://www.data.gov.in/catalog/electricity-consumption-bengaluru-city-0",
        note: "File is intentionally empty — BESCOM only provides city-level aggregates", available: false
      }
    ];

    tbody.innerHTML = REGISTRY.map(function (row) {
      var fnColor = row.available ? "var(--accent-cyan)" : "var(--text-muted)";
      var badge = row.available
        ? "<span style='font-size:10px;font-weight:700;color:#10b981;border:1px solid #10b981;padding:1px 6px;border-radius:3px'>Available</span>"
        : "<span style='font-size:10px;font-weight:700;color:#f43f5e;border:1px solid #f43f5e;padding:1px 6px;border-radius:3px'>Unavailable</span>";
      return "<tr>" +
        "<td>" + badge + "<br><code style='font-size:10px;color:" + fnColor + ";word-break:break-all'>" + esc(row.filename) + "</code></td>" +
        "<td style='font-size:12px'>" + esc(row.area) + "</td>" +
        "<td style='font-size:11px;color:var(--text-secondary)'>" + esc(row.metrics) + "</td>" +
        "<td><code style='font-size:11px'>" + esc(row.period) + "</code></td>" +
        "<td style='font-size:11px'>" +
        (row.url
          ? "<a href='" + esc(row.url) + "' target='_blank' rel='noopener noreferrer' style='color:var(--accent-cyan)'>" + esc(row.publisher) + "</a>"
          : "<span style='color:var(--text-muted)'>" + esc(row.publisher) + "</span>") +
        (row.note ? "<br><span style='color:var(--accent-amber);font-size:10px'>&#9888; " + esc(row.note) + "</span>" : "") +
        "</td></tr>";
    }).join("");
  }

  function getJSON(url) {
    return fetch(url, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error(url + " HTTP " + r.status);
      return r.json();
    });
  }

  function start() {
    var BASE = (window.UrbanPulseAPI && window.UrbanPulseAPI.baseUrl) || "http://127.0.0.1:8000/api/v1";
    var loadingMsg = $("esg-survey-loading");

    Promise.all([
      getJSON("data/esg/water_quality_lakes_2020_21.json"),
      getJSON(BASE + "/esg/electricity").catch(function (e) { console.warn("Electricity API:", e); return null; }),
      getJSON("data/esg/air_quality_stations.json").catch(function () { return null; })
    ]).then(function (results) {
      var waterData = results[0];
      var elecData  = results[1];
      var airData   = results[2];

      var wqByArea = waterByArea(waterData);
      renderWaterMap(wqByArea);
      renderWaterTable(wqByArea);
      renderElecChart(elecData);
      renderDatasetTable(waterData, elecData, airData);

      if (loadingMsg) loadingMsg.style.display = "none";
    }).catch(function (e) {
      console.error("ESG survey section failed:", e);
      if (loadingMsg) {
        loadingMsg.style.color = "var(--accent-rose)";
        loadingMsg.textContent = "Failed to load survey data: " + e.message;
      }
    });
  }

  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
  }
})();
