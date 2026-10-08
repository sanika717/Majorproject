/**
 * UrbanPulse – ESG Demo Data + AQI Card Populator
 *
 * 1. Live AQI card: reads from window.URBANPULSE_ESG_DATA (set by esg-env.js)
 *    once it is available. Shows AQI, category, source, last updated.
 *
 * 2. Year selector: adds demo years (2021, 2022, 2023) to the ESG year dropdown
 *    so Social/Governance demo scores can be shown alongside real Environmental data.
 *
 * 3. Demo Social/Governance: patches into the esg-scorecard render cycle by
 *    overriding the score display for the year selector's value.
 *
 * IMPORTANT: Social and Governance scores in this file are DEMO/PLACEHOLDER only.
 * Environmental values remain sourced from real datasets via esg-env.js.
 */

(function () {
  "use strict";

  var $ = function (id) { return document.getElementById(id); };

  // ─── AQI Category mapping (India AQI scale) ────────────────────────────────
  var AQI_CATEGORIES = [
    { max: 50,  label: "Good",          color: "#10b981" },
    { max: 100, label: "Satisfactory",  color: "#84cc16" },
    { max: 200, label: "Moderate",      color: "#f59e0b" },
    { max: 300, label: "Poor",          color: "#f97316" },
    { max: 400, label: "Very Poor",     color: "#ef4444" },
    { max: Infinity, label: "Severe",   color: "#7c3aed" }
  ];

  function aqiCategory(aqi) {
    for (var i = 0; i < AQI_CATEGORIES.length; i++) {
      if (aqi <= AQI_CATEGORIES[i].max) return AQI_CATEGORIES[i];
    }
    return AQI_CATEGORIES[AQI_CATEGORIES.length - 1];
  }

  // Compute a simple composite AQI from pollutant means (PM2.5-dominant)
  function computeAQI(data) {
    if (!data) return null;
    var air = data.air || {};
    var live = air.live;
    var mean = live && live.city_mean ? live.city_mean : (air.city_average || {});
    var naaqs = air.naaqs_annual || {};

    // Use PM2.5 if available (most representative for Bengaluru urban)
    if (mean.pm25 && naaqs.pm25) {
      // Simple linear sub-index (Indian AQI standard: 0–500)
      return Math.round((mean.pm25 / naaqs.pm25) * 100);
    }
    // Fall back to PM10
    if (mean.pm10 && naaqs.pm10) {
      return Math.round((mean.pm10 / naaqs.pm10) * 100);
    }
    return null;
  }

  function populateAQICard(data) {
    var aqi = computeAQI(data);
    var aqiEl = $("esg-aqi-value");
    var catEl = $("esg-aqi-category");
    var srcEl = $("esg-aqi-source");
    var updEl = $("esg-aqi-updated");

    if (aqi == null) {
      if (aqiEl) aqiEl.textContent = "—";
      if (catEl) catEl.textContent = "Air quality data not available for this period";
      return;
    }

    var cat = aqiCategory(aqi);
    if (aqiEl) {
      aqiEl.textContent = aqi;
      aqiEl.style.color = cat.color;
    }
    if (catEl) {
      catEl.innerHTML = '<span style="color:' + cat.color + ';font-weight:700">' + cat.label + '</span>';
    }

    var air = (data && data.air) || {};
    var live = air.live;
    var sources = air.sources || [];
    var srcLabel = "KSPCB / CPCB station data";
    if (sources.length) {
      var s = sources[0];
      srcLabel = (s.publisher || s.title || srcLabel);
    }
    if (srcEl) srcEl.textContent = "Source: " + srcLabel + (live ? " (live reading)" : " · Reporting period: " + (air.year || "—"));

    var updated = (live && live.last_updated) || air.retrieved_at;
    if (updEl && updated) updEl.textContent = "Last updated: " + updated;
  }

  // ─── Demo year-wise scores ─────────────────────────────────────────────────
  var DEMO_SCORES = {
    social:     { 2021: 54.2, 2022: 57.8, 2023: 61.3 },
    governance: { 2021: 46.1, 2022: 49.5, 2023: 52.7 }
  };
  var DEMO_YEARS = [2023, 2022, 2021];

  function addDemoYears() {
    var sel = $("esg-year-select");
    if (!sel) return;

    DEMO_YEARS.forEach(function (yr) {
      var already = false;
      for (var i = 0; i < sel.options.length; i++) {
        if (sel.options[i].value === String(yr)) { already = true; break; }
      }
      if (!already) {
        var opt = document.createElement("option");
        opt.value = String(yr);
        opt.textContent = yr + " [incl. demo]";
        // Insert in descending order before existing options
        var inserted = false;
        for (var j = 0; j < sel.options.length; j++) {
          var yrJ = parseInt(sel.options[j].value.match(/\d{4}/), 10) || 0;
          if (yr > yrJ) {
            sel.insertBefore(opt, sel.options[j]);
            inserted = true;
            break;
          }
        }
        if (!inserted) sel.appendChild(opt);
      }
    });

    // Re-enable selector if disabled
    if (sel.options.length) sel.disabled = false;
  }

  function applyDemoScores(period) {
    var yr = parseInt((period || "").match(/\d{4}/), 10);
    if (!yr) return;

    var sVal = $("esg-S-value"), sSub = $("esg-S-sub");
    var gVal = $("esg-G-value"), gSub = $("esg-G-sub");
    var oVal = $("esg-O-value"), oSub = $("esg-O-sub");

    var s = DEMO_SCORES.social[yr];
    var g = DEMO_SCORES.governance[yr];

    if (s != null && sVal) {
      sVal.textContent = s.toFixed(1) + " / 100";
      if (sSub) sSub.textContent = "⚠️ DEMO placeholder — not from a verified source";
    }
    if (g != null && gVal) {
      gVal.textContent = g.toFixed(1) + " / 100";
      if (gSub) gSub.textContent = "⚠️ DEMO placeholder — not from a verified source";
    }

    // If Environmental score is also numeric, try computing a partial composite
    var eVal = $("esg-E-value");
    var eScore = eVal && eVal.textContent ? parseFloat(eVal.textContent) : null;
    if (oVal && s != null && g != null && eScore != null && !isNaN(eScore)) {
      var composite = ((eScore + s + g) / 3).toFixed(1);
      oVal.textContent = composite + " / 100";
      oVal.style.color = "var(--accent-amber)";
      if (oSub) oSub.textContent = "⚠️ Partial composite: Environmental (real) + Social + Governance (DEMO). Carbon excluded.";
    }
  }

  function hookYearSelector() {
    var sel = $("esg-year-select");
    if (!sel) return;
    var orig = sel.onchange;
    sel.onchange = function () {
      if (orig) orig.call(this);
      // After scorecard renders, apply demo scores
      setTimeout(function () { applyDemoScores(sel.value); }, 50);
    };
    // Apply immediately for current value
    setTimeout(function () { applyDemoScores(sel.value); }, 100);
  }

  // ─── Bootstrap ─────────────────────────────────────────────────────────────
  document.addEventListener("DOMContentLoaded", function () {
    // Wait for ESG_ENV to finish loading (it sets window.URBANPULSE_ESG_DATA)
    var attempts = 0;
    function tryPopulate() {
      attempts++;
      if (window.URBANPULSE_ESG_DATA) {
        populateAQICard(window.URBANPULSE_ESG_DATA);
        addDemoYears();
        hookYearSelector();
        return;
      }
      if (attempts < 30) {
        setTimeout(tryPopulate, 300);
      } else {
        // Populate with nothing (show "—")
        populateAQICard(null);
        addDemoYears();
        hookYearSelector();
      }
    }
    tryPopulate();
  });

})();
