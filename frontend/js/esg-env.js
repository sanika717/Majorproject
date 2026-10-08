/**
 * UrbanPulse - ESG Environmental data layer (API first, cached JSON fallback).
 * Renders: area-wise air map, carbon chart, lake water quality, electricity panel.
 * Feeds verified values into esg.js scoring via URBANPULSE_ESG.addOfficial / setGhg.
 * Renders supplied values and their source links.
 */
(function () {
  "use strict";
  var $ = function (id) { return document.getElementById(id); };
  var esc = function (s) { return String(s == null ? "" : s).replace(/[&<>"]/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]; }); };
  var API = window.UrbanPulseAPI && window.UrbanPulseAPI.baseUrl || window.location.origin + "/api/v1", SRC = {};
  var getJSON = function (u) { return fetch(u, { cache: "no-store" }).then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); }); };
  function loaded(data, normalize, via) {
    var result = normalize(data);
    result.retrieved_at = new Date().toISOString();
    return { d: result, via: via };
  }
  function fetchEp(ep, file, norm) {
    var fb = function () { return getJSON("data/esg/" + file).then(function (d) { return loaded(d, norm, "bundled source data"); }); };
    return (API ? getJSON(API + "/esg/" + ep).then(function (d) { return loaded(d, norm, "ESG API"); }) : Promise.reject()).catch(fb);
  }
  var srcOf = function (c) { return SRC[c] ? [SRC[c]] : []; };
  var N = {
    air: function (d) {
      d.sources = d.sources && d.sources.length ? d.sources : srcOf(d.source_code).concat(srcOf(d.benchmark_source_code));
      return d;
    },
    carbon: function (d) {
      d.years_available = d.series.map(function (r) { return r.year; }).filter(function (y, i, a) { return a.indexOf(y) === i; });
      d.sources = d.sources && d.sources.length ? d.sources : srcOf(d.source_code);
      return d;
    },
    water: function (d) {
      if (!d.stations) return d;
      var mon = 0, sat = 0, cls = {}, ok = [];
      d.stations.filter(function (s) { return s.region === "Bangalore Urban"; }).forEach(function (s) {
        s.months.forEach(function (m) { if (!m["class"]) return; mon++; cls[m["class"]] = (cls[m["class"]] || 0) + 1;
          if (m.wqi === "S") { sat++; ok.push({ station: s.name, month: m.m, "class": m["class"] }); } });
      });
      return { period: d.source.period, station_months_monitored: mon, station_months_satisfactory: sat,
        pct_satisfactory: mon ? Math.round(sat / mon * 10000) / 100 : null, class_counts: cls, satisfactory_readings: ok,
        stations_total: d.stations.filter(function (s) { return s.region === "Bangalore Urban"; }).length,
        scope: "Bangalore Urban district lake/tank stations", sources: [d.source] };
    },
    elec: function (d) { d.sources = d.sources && d.sources.length ? d.sources : srcOf(d.reference_source_code); return d; }
  };
  var src = function (o) {
    return '<p class="esg-src">' + (o.sources || []).map(function (s) {
      var url = s && s.url ? String(s.url).trim() : "";
      if (/^https:\/\//i.test(url)) {
        return '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer">Dataset</a>';
      }
      return '<span>Dataset</span>';
    }).join("<br>") + "</p>";
  };
  var CAT = { C: "Commercial", T: "Traffic", I: "Industrial", H: "Hospital", R: "Residential" };
  function hideCard(element) {
    var card = element && element.closest(".chart-card");
    if (card) card.hidden = true;
  }
  function hideChart(element) {
    var chart = element && element.closest(".chart-wrapper");
    if (chart) chart.hidden = true;
  }

  function airMap(A) {
    var d = A.d, lim = d.naaqs_annual, host = $("esg-map");
    $("esg-air-src").innerHTML = src({ sources: d.sources });
    if (typeof L === "undefined") { hideCard(host); return; }
    var map = L.map("esg-map").setView([12.9716, 77.5946], 11);
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { maxZoom: 19, attribution: "&copy; OpenStreetMap contributors" }).addTo(map);
    function detail(s) {
      var rows = [["PM2.5", "pm25"], ["PM10", "pm10"], ["NO2", "no2"], ["SO2", "so2"], ["NH3", "nh3"], ["Lead", "lead"], ["CO", "co"]]
        .filter(function (p) { return s[p[1]] != null; }).map(function (p) {
          return "<tr><td>" + p[0] + "</td><td>" + esc(s[p[1]]) + " &micro;g/m&sup3;</td></tr>";
        }).join("");
      return "<h4>" + esc(s.name) + "</h4>" + (rows ? '<table class="custom-table"><thead><tr><th>Pollutant</th><th>Annual mean</th></tr></thead><tbody>' + rows + "</tbody></table>" : "");
    }
    var stationDetail = $("esg-station-detail");
    stationDetail.innerHTML = "";
    hideCard(stationDetail);
    d.stations.forEach(function (s) {
      if (s.lat == null || s.lng == null) return;
      var v = s.pm25 != null ? s.pm25 / lim.pm25 : (s.pm10 != null ? s.pm10 / lim.pm10 : null);
      var col = v == null ? "#94a3b8" : v <= 1 ? "#10b981" : v <= 1.5 ? "#f59e0b" : "#f43f5e";
      var m = L.circleMarker([s.lat, s.lng], { radius: 11, color: "#0a0e17", weight: 2, fillColor: col, fillOpacity: 0.9 }).addTo(map);
      m.bindPopup(detail(s), { maxWidth: 320 });
      m.on("click", function () {
        stationDetail.closest(".chart-card").hidden = false;
        stationDetail.innerHTML = detail(s);
      });
    });
    $("esg-air-unmapped").innerHTML = "";
    $("esg-air-src").innerHTML = src({ sources: d.sources });
  }

  function carbon(C) {
    var d = C.d, tot = d.series.filter(function (r) { return r.sector === "Total"; })[0], secs = d.series.filter(function (r) { return r.sector !== "Total" && r.mmt_co2e != null && !r.derived; });
    if (!tot || tot.mmt_co2e == null) { hideCard($("esg-carbon-kpi")); return; }
    $("esg-carbon-kpi").innerHTML = "<strong>" + esc(tot.mmt_co2e) + " million tCO2e</strong> (" + esc(tot.year) + ")";
    if (typeof Chart !== "undefined" && secs.length) new Chart($("esg-chart-carbon"), { type: "bar",
      data: { labels: secs.map(function (r) { return r.sector + " (" + r.share_pct + "%)"; }), datasets: [{ label: "million tCO2e, " + tot.year, data: secs.map(function (r) { return r.mmt_co2e; }), backgroundColor: ["#6366f1", "#38bdf8", "#f59e0b"], borderRadius: 6 }] },
      options: { indexAxis: "y", responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } } });
    else hideChart($("esg-chart-carbon"));
    $("esg-carbon-src").innerHTML = src({ sources: d.sources });
  }

  function water(W) {
    var d = W.d;
    if (d.pct_satisfactory == null) { hideCard($("esg-water-kpi")); return; }
    $("esg-water-kpi").innerHTML = "<strong>" + d.pct_satisfactory + "%</strong> of monitored station-months satisfactory (" + d.station_months_satisfactory + " / " + d.station_months_monitored + ")";
    var k = Object.keys(d.class_counts);
    if (typeof Chart !== "undefined" && k.length) new Chart($("esg-chart-water"), { type: "bar", data: { labels: k.map(function (c) { return "Class " + c; }),
      datasets: [{ label: "station-months", data: k.map(function (c) { return d.class_counts[c]; }), backgroundColor: "#38bdf8", borderRadius: 6 }] },
      options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } } });
    else hideChart($("esg-chart-water"));
    $("esg-water-src").innerHTML = src({ sources: d.sources });
  }

  function elec(E) {
    var d = E.d;
    if (!d.available || !d.rows.length) { hideCard($("esg-elec-body")); return; }
    $("esg-elec-body").innerHTML = '<table class="custom-table"><thead><tr><th>Area</th><th>Category</th><th>Year</th><th>Lakh units</th></tr></thead><tbody>' + d.rows.map(function (r) {
      return "<tr><td>" + esc(r.area) + "</td><td>" + esc(r.category || "-") + "</td><td>" + esc(r.year) + "</td><td>" + r.value_lakh_units + "</td></tr>"; }).join("") + "</tbody></table>";
    $("esg-elec-src").innerHTML = src({ sources: d.sources });
  }

  function run() {
    return getJSON("data/esg/sources.json").then(function (a) { a.forEach(function (s) { SRC[s.code] = s; }); }, function () {}).then(function () {
      return Promise.all([fetchEp("air-quality", "air_quality_stations.json", N.air), fetchEp("carbon-emissions", "carbon_emissions.json", N.carbon),
        fetchEp("water-quality", "water_quality_lakes_2020_21.json", N.water), fetchEp("electricity", "electricity_consumption.json", N.elec)]);
    }).then(function (r) {
      var A = r[0], C = r[1], W = r[2], E = r[3];
      window.URBANPULSE_ESG_DATA = { air: A.d, carbon: C.d, water: W.d, electricity: E.d, sources: SRC };
      [[airMap, A], [carbon, C], [water, W], [elec, E]].forEach(function (p) { try { p[0](p[1]); } catch (e) { console.error("ESG env panel failed:", e); } });
      return window.URBANPULSE_ESG_DATA;
    });
  }
  window.ESG_ENV = { ready: null };
  document.addEventListener("DOMContentLoaded", function () { /* started by esg.js so scoring waits for this */ });
  window.ESG_ENV.start = run;
})();
