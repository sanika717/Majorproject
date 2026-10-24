/**
 * UrbanPulse - Area-wise ESG scoring (Bengaluru)
 *
 * Every number is CALCULATED from the registered datasets in data/esg/*.json.
 * Nothing is typed in by hand except the area centroids (approximate, for distance
 * calculation only) and the published CPCB class ordering / NAAQS limits.
 *
 * ---------------------------------------------------------------------------
 * FORMULA
 * ---------------------------------------------------------------------------
 * AIR score of area a (0-100)
 *   For each pollutant p in {PM2.5, PM10, NO2, SO2, NH3, Lead}:
 *     C_p(a) = inverse-distance-weighted (power 2) mean of the annual means measured
 *              at KSPCB stations that have coordinates:  sum(C_i / d_i^2) / sum(1 / d_i^2)
 *     sub_p  = 100 * min(1, NAAQS_p / C_p(a))      (100 = meets the CPCB annual standard;
 *                                                    halves when concentration is 2x the limit)
 *   AIR(a) = min of sub_p  (AQI approach: the worst pollutant governs the score)
 *   Air is scored only if a mapped station lies within 10 km of the area centre; otherwise it is
 *   left out (not guessed) and ENVIRONMENTAL uses water alone, with confidence "Low".
 *
 * WATER score of area a (0-100)
 *   Each monitored lake/tank station-month gets points from its CPCB water-quality class:
 *     A=100, B=80, C=60, D=40, E=20      (CPCB "designated best use" order, A best, E worst)
 *   WATER(a) = mean points of all monitored station-months in the area (KSPCB MINARS 2020-21)
 *
 * ENVIRONMENTAL(a) = equally weighted mean of AIR(a) and WATER(a)
 *   (an indicator with no data for the area is dropped and the weights re-normalised)
 *
 * SOCIAL / GOVERNANCE: no area-level dataset is registered yet. They are NOT estimated.
 * OVERALL ESG(a) = weighted mean of the pillars that have a score (E 40 / S 30 / G 30),
 *   re-normalised over the available pillars, and shown with the pillar coverage.
 */
(function () {
  "use strict";

  var CLASS_POINTS = { A: 100, B: 80, C: 60, D: 40, E: 20 };
  var MAX_AIR_KM = 10;   // beyond this distance from any station, air is NOT scored for the area
  var PILLAR_WEIGHTS = { E: 0.4, S: 0.3, G: 0.3 };
  var AIR_KEYS = { pm25: "PM2.5", pm10: "PM10", no2: "NO2", so2: "SO2", nh3: "NH3", lead: "Lead" };

  // Approximate area centres (lat, lng) used only to measure distance to monitoring stations.
  var AREAS = [
    { id: "bommanahalli", name: "Bommanahalli", lat: 12.905, lng: 77.625, tag: "Bommanahalli" },
    { id: "mahadevapura", name: "Mahadevapura", lat: 12.990, lng: 77.700, tag: "Mahadevapura" },
    { id: "dasarahalli", name: "Dasarahalli", lat: 13.045, lng: 77.500, tag: "Dasarahalli" },
    { id: "yelahanka", name: "Yelahanka", lat: 13.100, lng: 77.590, tag: "Yelahanka" },
    { id: "rrnagar", name: "Rajarajeshwari Nagar", lat: 12.930, lng: 77.500, tag: "Rajarajeswarinagara" },
    { id: "south", name: "Bengaluru South", lat: 12.930, lng: 77.580, tag: "BNG-City South" },
    { id: "east", name: "Bengaluru East", lat: 12.980, lng: 77.630, tag: "BNG-City East" },
    { id: "west", name: "Bengaluru West", lat: 12.990, lng: 77.540, tag: "BNG-City - West" },
    { id: "peenya", name: "Peenya", lat: 13.030, lng: 77.520, tag: "Peenya" },
    { id: "sarjapura", name: "Sarjapura", lat: 12.860, lng: 77.780, tag: "Sarjapura" },
    { id: "anekal", name: "Anekal", lat: 12.710, lng: 77.690, tag: "Anekal" }
  ];

  var isNum = function (v) { return typeof v === "number" && isFinite(v); };
  var mean = function (a) { return a.length ? a.reduce(function (s, v) { return s + v; }, 0) / a.length : null; };

  function km(lat1, lng1, lat2, lng2) {
    var R = 6371, rad = Math.PI / 180;
    var dLat = (lat2 - lat1) * rad, dLng = (lng2 - lng1) * rad;
    var h = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.cos(lat1 * rad) * Math.cos(lat2 * rad) * Math.sin(dLng / 2) * Math.sin(dLng / 2);
    return 2 * R * Math.asin(Math.sqrt(h));
  }

  function airForArea(area, air) {
    var stations = (air.stations || []).filter(function (s) { return isNum(s.lat) && isNum(s.lng); });
    var limits = air.naaqs_annual || {};
    var nearest = Infinity, nearestName = "";
    stations.forEach(function (s) {
      var d = km(area.lat, area.lng, s.lat, s.lng);
      if (d < nearest) { nearest = d; nearestName = s.name; }
    });
    var subs = [], detail = [];
    Object.keys(AIR_KEYS).forEach(function (key) {
      if (!isNum(limits[key]) || limits[key] <= 0) return;
      var num = 0, den = 0;
      stations.forEach(function (s) {
        if (!isNum(s[key])) return;
        var d = Math.max(km(area.lat, area.lng, s.lat, s.lng), 0.5); // 0.5 km floor avoids divide-by-zero
        var w = 1 / (d * d);
        num += s[key] * w; den += w;
      });
      if (!den) return;
      var conc = num / den;
      var sub = 100 * Math.min(1, limits[key] / conc);
      subs.push(sub);
      detail.push({ pollutant: AIR_KEYS[key], concentration: conc, limit: limits[key], score: sub });
    });
    // AQI approach: the worst pollutant governs. Interpolation is only trusted within MAX_AIR_KM of a station.
    var covered = nearest <= MAX_AIR_KM && subs.length > 0;
    return { score: covered ? Math.min.apply(null, subs) : null, detail: detail, nearestKm: nearest,
      nearestStation: nearestName, covered: covered,
      governing: covered ? detail.filter(function (d) { return d.score === Math.min.apply(null, subs); })[0].pollutant : null };
  }

  function waterForArea(area, water) {
    var pts = [], satisfactory = 0, stationCount = 0;
    (water.stations || []).forEach(function (st) {
      var m = /\(([^)]+)\)/.exec(st.district || "");
      if (!m || m[1].trim() !== area.tag) return;
      var counted = false;
      (st.months || []).forEach(function (mo) {
        if (!mo["class"] || !isNum(CLASS_POINTS[mo["class"]])) return;
        pts.push(CLASS_POINTS[mo["class"]]);
        if (mo.wqi === "S") satisfactory++;
        counted = true;
      });
      if (counted) stationCount++;
    });
    return {
      score: mean(pts), stationMonths: pts.length, stations: stationCount,
      pctSatisfactory: pts.length ? 100 * satisfactory / pts.length : null
    };
  }

  function confidence(airRes, waterRes) {
    var airOk = isNum(airRes.score) && airRes.nearestKm <= 6;
    if (!isNum(airRes.score)) return "Low";
    var waterOk = isNum(waterRes.score) && waterRes.stationMonths >= 20;
    if (airOk && waterOk) return "High";
    if ((airOk && isNum(waterRes.score)) || (waterOk && isNum(airRes.score))) return "Medium";
    return "Low";
  }

  function combine(parts) {            // equal weights, drops nulls, re-normalises
    var v = parts.filter(isNum);
    return v.length ? mean(v) : null;
  }

  function overall(pillars) {
    var num = 0, den = 0, used = [];
    Object.keys(PILLAR_WEIGHTS).forEach(function (k) {
      if (isNum(pillars[k])) { num += pillars[k] * PILLAR_WEIGHTS[k]; den += PILLAR_WEIGHTS[k]; used.push(k); }
    });
    return { score: den ? num / den : null, pillars: used };
  }

  function compute(data) {
    var air = data.air || {}, water = data.water || {};
    var rows = AREAS.map(function (area) {
      var a = airForArea(area, air), w = waterForArea(area, water);
      var env = combine([a.score, w.score]);
      var o = overall({ E: env, S: null, G: null });
      return {
        id: area.id, name: area.name, lat: area.lat, lng: area.lng,
        air: a, water: w, environmental: env, social: null, governance: null,
        overall: o.score, pillars: o.pillars, confidence: confidence(a, w)
      };
    });
    rows.sort(function (x, y) { return (y.overall || -1) - (x.overall || -1); });
    rows.forEach(function (r, i) { r.rank = isNum(r.overall) ? i + 1 : null; });
    return rows;
  }

  // ------------------------------------------------------------------ rendering
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); };
  var fmt = function (v) { return isNum(v) ? v.toFixed(1) : "—"; };
  function colour(v) { return !isNum(v) ? "#94a3b8" : v >= 70 ? "#10b981" : v >= 50 ? "#f59e0b" : "#f43f5e"; }
  function grade(v) { return !isNum(v) ? "n/a" : v >= 80 ? "A" : v >= 65 ? "B" : v >= 50 ? "C" : v >= 35 ? "D" : "E"; }

  function render(rows, data) {
    var body = $("esg-area-rows");
    if (!body) return;
    body.innerHTML = rows.map(function (r) {
      return "<tr data-area='" + esc(r.id) + "'><td>" + (r.rank || "—") + "</td><th scope='row'>" + esc(r.name) + "</th>" +
        "<td>" + fmt(r.air.score) + "</td><td>" + fmt(r.water.score) + "</td><td>" + fmt(r.environmental) + "</td>" +
        "<td title='No area-level dataset registered'>Pending</td><td title='No area-level dataset registered'>Pending</td>" +
        "<td><strong style='color:" + colour(r.overall) + "'>" + fmt(r.overall) + "</strong> <small>(" + grade(r.overall) + ")</small></td>" +
        "<td>" + esc(r.confidence) + "</td></tr>";
    }).join("");

    var cityEnv = mean(rows.map(function (r) { return r.environmental; }).filter(isNum));
    var kpi = $("esg-area-kpi");
    if (kpi) {
      var best = rows[0], worst = rows.filter(function (r) { return isNum(r.overall); }).slice(-1)[0];
      kpi.innerHTML = "<strong>Bengaluru average (Environmental): " + fmt(cityEnv) + " / 100</strong> across " + rows.length + " areas · " +
        "Best: <strong>" + esc(best.name) + "</strong> (" + fmt(best.overall) + ") · Lowest: <strong>" + esc(worst.name) + "</strong> (" + fmt(worst.overall) + ")";
    }

    var detail = $("esg-area-detail");
    function show(r) {
      if (!detail) return;
      var air = r.air.detail.map(function (d) {
        return "<tr><td>" + esc(d.pollutant) + "</td><td>" + d.concentration.toFixed(1) + "</td><td>" + d.limit + "</td><td>" + d.score.toFixed(1) + "</td></tr>";
      }).join("");
      detail.innerHTML = "<h4>" + esc(r.name) + " — ESG " + fmt(r.overall) + " / 100</h4>" +
        "<p>Environmental " + fmt(r.environmental) + " = mean(Air " + fmt(r.air.score) + ", Water " + fmt(r.water.score) + ")" +
        (r.air.covered ? " · Air governed by " + esc(r.air.governing) : " · Air not scored (no station within 10 km)") + "</p>" +
        "<p>Nearest air station: " + esc(r.air.nearestStation) + " (" + r.air.nearestKm.toFixed(1) + " km)</p>" +
        "<table class='custom-table'><thead><tr><th>Pollutant</th><th>Est. µg/m³</th><th>CPCB limit</th><th>Sub-score</th></tr></thead><tbody>" + air + "</tbody></table>" +
        "<p style='margin-top:8px'>Water: " + r.water.stations + " lakes/tanks, " + r.water.stationMonths + " station-months; " +
        (isNum(r.water.pctSatisfactory) ? r.water.pctSatisfactory.toFixed(1) + "% satisfactory" : "no monitored months") + ".</p>";
    }
    show(rows[0]);
    body.querySelectorAll("tr").forEach(function (tr) {
      tr.style.cursor = "pointer";
      tr.addEventListener("click", function () {
        var r = rows.filter(function (x) { return x.id === tr.getAttribute("data-area"); })[0];
        if (r) show(r);
      });
    });

    if (typeof L !== "undefined" && $("esg-area-map") && !$("esg-area-map")._leaflet_id) {
      var map = L.map("esg-area-map").setView([12.99, 77.6], 10);
      L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
      rows.forEach(function (r) {
        var m = L.circleMarker([r.lat, r.lng], { radius: 16, color: "#0a0e17", weight: 2, fillColor: colour(r.overall), fillOpacity: 0.85 }).addTo(map);
        m.bindTooltip(r.name + ": " + fmt(r.overall), { permanent: true, direction: "center", className: "esg-area-label" });
        m.on("click", function () { show(r); });
      });
    }

    var links = $("esg-area-sources");
    if (links) {
      var src = data.sources || [];
      links.innerHTML = src.map(function (s) {
        return "<li><a href='" + esc(s.url) + "' target='_blank' rel='noopener noreferrer'>" + esc(s.title) + "</a> — " + esc(s.publisher) + " (" + esc(s.period) + ")</li>";
      }).join("");
    }
  }

  function getJSON(u) { return fetch(u, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); }); }

  function start() {
    Promise.all([
      getJSON("data/esg/air_quality_stations.json"),
      getJSON("data/esg/water_quality_lakes_2020_21.json"),
      getJSON("data/esg/sources.json")
    ]).then(function (r) {
      var wanted = { GUTTIKUNDA_2019: 1, CPCB_NAAQS: 1, KSPCB_MINARS_2020_21: 1 };
      var data = { air: r[0], water: r[1], sources: r[2].filter(function (s) { return wanted[s.code]; }) };
      var rows = compute(data);
      // Publish area-wise results so the scorecard summary cards can read averages
      window.URBANPULSE_AREAS_RESULT = rows;
      render(rows, data);
      // Trigger scorecard re-render so Environmental & Overall ESG cards pick up area averages
      try {
        var sel = document.getElementById("esg-year-select");
        if (sel && sel.value) sel.dispatchEvent(new Event("change"));
      } catch (e) { /* scorecard not ready yet */ }
    }).catch(function (e) {
      console.error("Area ESG failed:", e);
      var body = $("esg-area-rows");
      if (body) body.innerHTML = "<tr><td colspan='9'>Could not load the ESG datasets.</td></tr>";
    });
  }

  if (typeof window !== "undefined") window.URBANPULSE_ESG_AREAS = { compute: compute, AREAS: AREAS };
  if (typeof module !== "undefined" && module.exports) module.exports = { compute: compute, AREAS: AREAS };
  if (typeof document !== "undefined") {
    if (document.readyState === "loading") {
      document.addEventListener("DOMContentLoaded", start);
    } else {
      start();
    }
  }
})();
