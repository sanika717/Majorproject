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

  var AQI_SCALE = [
    { max: 50,       label: "Good",          color: "#10b981", pct: 0 },
    { max: 100,      label: "Satisfactory",  color: "#84cc16", pct: 16.7 },
    { max: 200,      label: "Moderate",      color: "#f59e0b", pct: 33.3 },
    { max: 300,      label: "Poor",          color: "#f97316", pct: 50 },
    { max: 400,      label: "Very Poor",     color: "#ef4444", pct: 66.7 },
    { max: Infinity, label: "Severe",        color: "#7c3aed", pct: 83.3 }
  ];

  function aqiCategory(aqi) {
    for (var i = 0; i < AQI_SCALE.length; i++) {
      if (aqi <= AQI_SCALE[i].max) return AQI_SCALE[i];
    }
    return AQI_SCALE[AQI_SCALE.length - 1];
  }

  function calcLocalCPCB(pm25, pm10) {
    function sub(v, bp) {
      if (v == null || isNaN(v)) return 0;
      for (var i = 0; i < bp.length; i++) {
        var bLo = bp[i][0], bHi = bp[i][1], iLo = bp[i][2], iHi = bp[i][3];
        if (v >= bLo && v <= bHi) return Math.round(iLo + (iHi - iLo) * (v - bLo) / (bHi - bLo));
      }
      if (v > bp[bp.length - 1][1]) {
        var last = bp[bp.length - 1];
        return Math.round(last[3] + (v - last[1]));
      }
      return 0;
    }
    var bp25 = [[0, 30, 0, 50], [31, 60, 51, 100], [61, 90, 101, 200], [91, 120, 201, 300], [121, 250, 301, 400], [251, 350, 401, 500]];
    var bp10 = [[0, 50, 0, 50], [51, 100, 51, 100], [101, 250, 101, 200], [251, 350, 201, 300], [351, 430, 301, 400], [431, 500, 401, 500]];
    var i25 = sub(pm25, bp25);
    var i10 = sub(pm10, bp10);
    var score = Math.max(i25, i10);
    var cat = aqiCategory(score).label;
    var dom = i25 >= i10 ? "PM2.5" : "PM10";
    return { score: score, category: cat, dom: dom };
  }

  function formatISTFull(dateInput) {
    if (!dateInput) return "—";
    if (typeof dateInput === "string") {
      var m = dateInput.match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
      if (m) {
        var yr = parseInt(m[1], 10);
        var mo = parseInt(m[2], 10) - 1;
        var da = parseInt(m[3], 10);
        var hr = parseInt(m[4], 10);
        var mi = parseInt(m[5], 10);
        var days = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
        var months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
        var dObj = new Date(yr, mo, da, hr, mi);
        var dayName = days[dObj.getDay()];
        var monthName = months[mo];
        var dateNum = String(da).padStart(2, "0");
        var hour12 = hr % 12 || 12;
        var ampm = hr >= 12 ? "PM" : "AM";
        var hourStr = String(hour12).padStart(2, "0");
        var minStr = String(mi).padStart(2, "0");
        return dateNum + " " + monthName + " " + yr + ", " + dayName + ", " + hourStr + ":" + minStr + " " + ampm + " IST";
      }
    }
    try {
      var d = dateInput instanceof Date ? dateInput : new Date(dateInput);
      return new Intl.DateTimeFormat("en-IN", {
        timeZone: "Asia/Kolkata",
        day: "2-digit",
        month: "short",
        year: "numeric",
        weekday: "long",
        hour: "2-digit",
        minute: "2-digit",
        hour12: true
      }).format(d) + " IST";
    } catch (e) {
      return String(dateInput);
    }
  }

  function applyAQICard(aqi, categoryLabel, color, pollutant, sourceText, dataTimeFormatted, fetchTimeFormatted, isLive) {
    var valEl = $("esg-aqi-value"),
        catEl = $("esg-aqi-category"),
        polEl = $("esg-aqi-pollutant"),
        srcEl = $("esg-aqi-source"),
        dataTimeEl = $("esg-aqi-data-time"),
        fetchTimeEl = $("esg-aqi-fetch-time"),
        updEl = $("esg-aqi-updated"),
        dotEl = $("esg-aqi-live-dot"),
        needleWrap = $("esg-aqi-needle"),
        needle = $("esg-aqi-needle-arrow"),
        hintEl = $("esg-aqi-key-hint"),
        cardEl = $("esg-aqi-card");

    if (valEl) { valEl.textContent = aqi; valEl.style.color = color; }
    if (catEl) { catEl.textContent = categoryLabel; catEl.style.color = color; }
    if (polEl && pollutant) polEl.textContent = "Dominant pollutant: " + pollutant;
    if (srcEl) srcEl.textContent = sourceText || "Source: Live Atmospheric Monitoring · Bengaluru";
    if (dataTimeEl) dataTimeEl.textContent = dataTimeFormatted || "—";
    if (fetchTimeEl) fetchTimeEl.textContent = fetchTimeFormatted || "—";
    if (updEl) updEl.textContent = dataTimeFormatted || "";
    if (dotEl) dotEl.style.display = isLive ? "inline-block" : "none";
    if (hintEl) hintEl.style.display = "none";
    if (cardEl && color) cardEl.style.borderLeftColor = color;

    // Position needle on the scale bar (6 equal segments = 0..100%, 0 to 500 scale)
    if (needleWrap && needle && typeof aqi === "number") {
      var pct = Math.min(100, Math.max(0, (aqi / 500) * 100));
      needleWrap.style.display = "block";
      needle.style.left = pct + "%";
    }
  }

  var pmChartInstance = null;

  function renderPMTrendChart(timeline, currentPM25, currentPM10) {
    var loadingEl = $("esg-pm-chart-loading");
    var errorEl = $("esg-pm-chart-error");
    var wrapperEl = $("esg-pm-chart-wrapper");
    var canvasEl = $("esg-pm-trend-chart");
    var badge25 = $("esg-pm25-badge");
    var badge10 = $("esg-pm10-badge");

    if (badge25 && currentPM25 != null) badge25.textContent = Number(currentPM25).toFixed(1);
    if (badge10 && currentPM10 != null) badge10.textContent = Number(currentPM10).toFixed(1);

    if (!timeline || !timeline.length || !canvasEl) {
      if (loadingEl) loadingEl.style.display = "none";
      if (errorEl) errorEl.style.display = "block";
      if (wrapperEl) wrapperEl.style.display = "none";
      return;
    }

    if (loadingEl) loadingEl.style.display = "none";
    if (errorEl) errorEl.style.display = "none";
    if (wrapperEl) wrapperEl.style.display = "block";

    if (typeof Chart === "undefined") {
      console.warn("[UrbanPulse ESG] Chart.js not loaded, unable to render particulate trend");
      return;
    }

    if (pmChartInstance) {
      pmChartInstance.destroy();
      pmChartInstance = null;
    }

    var labels = timeline.map(function (item) { return item.label; });
    var dataPM25 = timeline.map(function (item) { return item.pm25; });
    var dataPM10 = timeline.map(function (item) { return item.pm10; });

    var ctx = canvasEl.getContext("2d");
    pmChartInstance = new Chart(ctx, {
      type: "line",
      data: {
        labels: labels,
        datasets: [
          {
            label: "PM2.5 (µg/m³)",
            data: dataPM25,
            borderColor: "#38bdf8",
            backgroundColor: "rgba(56, 189, 248, 0.12)",
            borderWidth: 2.5,
            fill: true,
            tension: 0.35,
            pointRadius: 3,
            pointHoverRadius: 6,
            pointBackgroundColor: "#38bdf8",
            pointBorderColor: "#0f172a",
            pointBorderWidth: 1.5
          },
          {
            label: "PM10 (µg/m³)",
            data: dataPM10,
            borderColor: "#f59e0b",
            backgroundColor: "rgba(245, 158, 11, 0.08)",
            borderWidth: 2.5,
            fill: true,
            tension: 0.35,
            pointRadius: 3,
            pointHoverRadius: 6,
            pointBackgroundColor: "#f59e0b",
            pointBorderColor: "#0f172a",
            pointBorderWidth: 1.5
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: {
          mode: "index",
          intersect: false
        },
        plugins: {
          legend: {
            display: false
          },
          tooltip: {
            backgroundColor: "rgba(15, 23, 42, 0.95)",
            titleColor: "#f8fafc",
            bodyColor: "#cbd5e1",
            borderColor: "rgba(255, 255, 255, 0.12)",
            borderWidth: 1,
            padding: 10,
            callbacks: {
              title: function (items) {
                if (!items || !items.length) return "";
                var idx = items[0].dataIndex;
                var pt = timeline[idx];
                return (pt && (pt.formatted_time || formatISTFull(pt.raw_time))) || items[0].label;
              },
              label: function (context) {
                var val = context.parsed.y != null ? context.parsed.y.toFixed(1) : "—";
                return context.dataset.label + ": " + val + " µg/m³";
              }
            }
          }
        },
        scales: {
          x: {
            grid: {
              color: "rgba(255, 255, 255, 0.05)",
              drawBorder: false
            },
            ticks: {
              color: "#94a3b8",
              font: { family: "Inter", size: 11 },
              maxTicksLimit: 12
            }
          },
          y: {
            beginAtZero: true,
            grid: {
              color: "rgba(255, 255, 255, 0.05)",
              drawBorder: false
            },
            ticks: {
              color: "#94a3b8",
              font: { family: "Inter", size: 11 },
              callback: function (value) { return value + " µg/m³"; }
            }
          }
        }
      }
    });
  }

  function fetchLiveAirQuality() {
    var loadingEl = $("esg-pm-chart-loading");
    var errorEl = $("esg-pm-chart-error");
    var wrapperEl = $("esg-pm-chart-wrapper");
    var valEl = $("esg-aqi-value");
    var catEl = $("esg-aqi-category");
    var polEl = $("esg-aqi-pollutant");

    if (loadingEl) loadingEl.style.display = "block";
    if (errorEl) errorEl.style.display = "none";
    if (wrapperEl) wrapperEl.style.display = "none";
    if (valEl) valEl.textContent = "…";
    if (catEl) { catEl.textContent = "Fetching live air quality…"; catEl.style.color = "var(--text-muted)"; }
    if (polEl) polEl.textContent = "Connecting to atmospheric monitoring feed…";

    var isHttp = window.location.protocol.startsWith("http");
    var host = window.location.hostname || "127.0.0.1";
    var port = window.location.port;
    var apiBase = (window.UrbanPulseAPI && window.UrbanPulseAPI.baseUrl)
      ? window.UrbanPulseAPI.baseUrl
      : (isHttp && port === "8000" ? "/api/v1" : "http://" + host + ":8000/api/v1");

    function handleSuccess(data) {
      var aqi = data.aqi != null ? data.aqi : 0;
      var cat = aqiCategory(aqi);
      var color = cat.color;
      var pol = data.dominantPollutant || (data.pm25 != null ? "PM2.5 (" + Number(data.pm25).toFixed(1) + " µg/m³)" : "");
      var source = data.source || "Live Atmospheric Monitoring · Bengaluru";
      var dataTimeFormatted = data.data_timestamp_formatted || formatISTFull(data.data_timestamp || data.dateTime);
      var fetchTimeFormatted = data.fetch_timestamp_formatted || formatISTFull(new Date());

      applyAQICard(aqi, (data.category || cat.label), color, pol, source, dataTimeFormatted, fetchTimeFormatted, true);
      renderPMTrendChart(data.timeline || [], data.pm25, data.pm10);
    }

    function fetchClientFallback() {
      var omUrl = "https://air-quality-api.open-meteo.com/v1/air-quality?latitude=12.9716&longitude=77.5946&current=european_aqi,us_aqi,pm10,pm2_5&hourly=pm10,pm2_5,us_aqi&timezone=Asia%2FKolkata&past_days=1&forecast_days=1";
      fetch(omUrl, { cache: "no-store" })
        .then(function (r) { if (!r.ok) throw new Error("Open-Meteo HTTP " + r.status); return r.json(); })
        .then(function (omData) {
          var curr = omData.current || {};
          var hourly = omData.hourly || {};
          var pm25 = curr.pm2_5;
          var pm10 = curr.pm10;
          var cpcb = calcLocalCPCB(pm25, pm10);
          var times = hourly.time || [];
          var p25s = hourly.pm2_5 || [];
          var p10s = hourly.pm10 || [];
          var currT = curr.time || "";
          var cIdx = times.length - 1;
          for (var i = 0; i < times.length; i++) {
            if (times[i] >= currT) { cIdx = i; break; }
          }
          var sIdx = Math.max(0, cIdx - 23);
          var tl = [];
          for (var j = sIdx; j <= cIdx; j++) {
            var raw = times[j];
            tl.push({
              raw_time: raw,
              label: raw.indexOf("T") >= 0 ? raw.split("T")[1] : raw,
              formatted_time: formatISTFull(raw),
              pm25: p25s[j],
              pm10: p10s[j]
            });
          }
          handleSuccess({
            aqi: cpcb.score,
            category: cpcb.category,
            dominantPollutant: cpcb.dom + " (" + (cpcb.dom === "PM2.5" ? pm25 : pm10) + " µg/m³)",
            pm25: pm25,
            pm10: pm10,
            data_timestamp: curr.time,
            data_timestamp_formatted: formatISTFull(curr.time),
            fetch_timestamp_formatted: formatISTFull(new Date()),
            dateTime: curr.time,
            source: "Open-Meteo / Copernicus CAMS · Bengaluru",
            timeline: tl
          });
        })
        .catch(function (err) {
          console.error("[UrbanPulse ESG] Live AQI fetch failed:", err);
          if (loadingEl) loadingEl.style.display = "none";
          if (errorEl) {
            errorEl.style.display = "block";
            var msgEl = $("esg-pm-chart-error-msg");
            if (msgEl) msgEl.textContent = "Live air quality API temporarily unavailable: " + err.message;
          }
          if (valEl) valEl.textContent = "—";
          if (catEl) { catEl.textContent = "Air quality data unavailable"; catEl.style.color = "var(--accent-rose)"; }
          if (polEl) polEl.textContent = "Please check your network connection and retry.";
        });
    }

    fetch(apiBase + "/esg/aqi", { cache: "no-store" })
      .then(function (r) {
        if (!r.ok) throw new Error("Backend AQI HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        if (data.status === "ok" && data.aqi != null) {
          handleSuccess(data);
        } else {
          fetchClientFallback();
        }
      })
      .catch(function () {
        fetchClientFallback();
      });
  }

  function run() {
    // 1. Fetch live AQI & 24h PM2.5 / PM10 line graph data immediately
    fetchLiveAirQuality();

    // 2. Fetch registered ESG datasets for indicators & scorecard
    return getJSON("data/esg/sources.json").then(function (a) {
      a.forEach(function (s) { SRC[s.code] = s; });
    }, function () {}).then(function () {
      return Promise.all([
        fetchEp("air-quality", "air_quality_stations.json", N.air),
        fetchEp("carbon-emissions", "carbon_emissions.json", N.carbon),
        fetchEp("water-quality", "water_quality_lakes_2020_21.json", N.water),
        fetchEp("electricity", "electricity_consumption.json", N.elec)
      ]);
    }).then(function (r) {
      var A = r[0], C = r[1], W = r[2], E = r[3];
      window.URBANPULSE_ESG_DATA = { air: A.d, carbon: C.d, water: W.d, electricity: E.d, sources: SRC };
      return window.URBANPULSE_ESG_DATA;
    });
  }

  window.ESG_ENV = {
    start: run,
    fetchLiveAQI: fetchLiveAirQuality
  };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      fetchLiveAirQuality();
    });
  } else {
    fetchLiveAirQuality();
  }
})();
