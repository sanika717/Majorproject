(function () {
  "use strict";

  var DATA = {};
  var CATEGORY_NAMES = { environmental: "Environmental", social: "Social", governance: "Governance", climate: "Carbon / Climate" };
  var POLLUTANTS = { so2: "SO2", no2: "NO2", pm10: "PM10", pm25: "PM2.5", nh3: "NH3", lead: "Lead", co: "CO" };
  var $ = function (id) { return document.getElementById(id); };
  var isNumber = function (value) { return typeof value === "number" && Number.isFinite(value); };
  var escapeHTML = function (value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
    });
  };

  function sourceFor(code, candidates) {
    var registry = DATA.sources && DATA.sources[code] || {};
    var found = (candidates || []).filter(function (source) { return source && source.code === code; })[0] || {};
    return Object.assign({}, registry, found);
  }

  function record(indicator, value, unit, period, source, geography, retrievedAt, method, score, category, relatedSources) {
    return {
      indicator: indicator,
      value: value,
      unit: unit,
      period: String(period),
      location: geography.location || source.location,
      geographic_level: geography.level || source.geographic_level,
      source_organization: source.publisher || "",
      source_title: source.title || "",
      source_url: source.url || "",
      source_urls: [source.url].concat((relatedSources || []).map(function (item) { return item && item.url; })).filter(Boolean),
      retrieved_at: retrievedAt || null,
      methodology: method || source.note || "",
      score: isNumber(score) ? score : null,
      category: category
    };
  }

  function latestTimestamp(rows) {
    var values = (rows || []).map(function (row) { return row.last_updated; }).filter(Boolean).sort();
    return values.length ? values[values.length - 1] : null;
  }

  function airRecords(period) {
    var air = DATA.air || {};
    var live = air.live;
    var isLive = live && live.scoring_eligible && live.period_label === period && live.city_mean;
    if (!isLive && String(air.year || "") !== period) return [];

    var values = isLive ? live.city_mean : air.city_average || {};
    var limits = air.naaqs_annual || {};
    var source = isLive ? sourceFor("CPCB_RT_AQI", [live.source]) : sourceFor(air.source_code, air.sources);
    var benchmark = sourceFor(air.benchmark_source_code || "CPCB_NAAQS", air.sources);
    if (!source.url || !benchmark.url) return [];
    var keys = Object.keys(POLLUTANTS).filter(function (key) {
      return isNumber(values[key]) && isNumber(limits[key]) && limits[key] > 0;
    });
    if (!keys.length) return [];

    var geography = {
      location: source.location || "Bengaluru",
      level: isLive ? "City aggregate from station readings" : "City average from KSPCB station observations"
    };
    var scoringMethod = "Pollutant headroom against CPCB annual standards: max(0, 1 - observed / standard) × 100. The environmental category equally weights its available scored indicators.";
    var retrieved = isLive ? live.last_updated : latestTimestamp(air.stations) || air.retrieved_at;
    return keys.map(function (key) {
      var indicatorScore = Math.max(0, Math.min(100, (1 - values[key] / limits[key]) * 100));
      return record(POLLUTANTS[key] + " annual mean", values[key], isLive ? live.unit : air.units, period,
        source, geography, retrieved, scoringMethod + " Benchmark: " + (benchmark.title || "CPCB NAAQS") + ".", indicatorScore, "environmental", [benchmark]);
    });
  }

  function waterRecords(period) {
    var water = DATA.water || {};
    if (!water.period || !isNumber(water.pct_satisfactory)) return [];
    var pStr = String(period).trim();
    var wStr = String(water.period).trim();
    var matches = (wStr === pStr) || (pStr === "2020-21" && (wStr.indexOf("2020") >= 0 || wStr.indexOf("2021") >= 0));
    if (!matches) return [];
    var source = sourceFor("KSPCB_MINARS_2020_21", water.sources);
    if (!source.url) return [];
    var geography = { location: source.location || water.scope, level: "Lake/tank station-month records within Bangalore Urban district" };
    var numerator = water.station_months_satisfactory;
    var denominator = water.station_months_monitored;
    var item = record("Satisfactory lake/tank station-months", water.pct_satisfactory, "%", period, source,
      geography, water.last_updated || water.retrieved_at, "Satisfactory monitored station-months divided by all monitored station-months, expressed as a percentage.",
      water.pct_satisfactory, "environmental");
    item.observation_count = isNumber(numerator) && isNumber(denominator) ? numerator + " / " + denominator : "";
    return [item];
  }

  function carbonRecords(period) {
    var carbon = DATA.carbon || {};
    var series = carbon.series || [];
    var total = series.filter(function (row) { return row.sector === "Total" && String(row.year) === period; })[0];
    if (!total || !isNumber(total.mmt_co2e)) return [];
    var source = sourceFor(total.source_code || carbon.source_code, carbon.sources);
    if (!source.url) return [];
    var geography = { location: total.boundary || source.location, level: source.geographic_level };
    var rows = [record("Total greenhouse-gas emissions", total.mmt_co2e, carbon.unit, total.year, source,
      geography, total.last_updated || carbon.retrieved_at, "Reported inventory total. No comparable source-backed benchmark or time series is available for scoring.",
      null, "climate")];
    series.filter(function (row) {
      return String(row.year) === period && row.sector !== "Total" && isNumber(row.share_pct);
    }).forEach(function (row) {
      rows.push(record(row.sector + " emissions share", row.share_pct, "%", row.year, source, geography,
        row.last_updated || carbon.retrieved_at, source.note, null, "climate"));
    });
    return rows;
  }

  function electricityRecords(period) {
    var electricity = DATA.electricity || {};
    var pNorm = String(period).replace(/^.*(\d{4})[^\d]+(\d{2,4}).*$/, "$1-$2");
    return (electricity.rows || []).filter(function (row) {
      var rYear = String(row.year).trim();
      return (rYear === String(period).trim() || rYear === pNorm) && isNumber(row.value_lakh_units);
    }).map(function (row) {
      var source = sourceFor(row.source_code, electricity.sources);
      return record(row.category || "Electricity consumption", row.value_lakh_units, "lakh units", row.year, source,
        { location: row.area, level: source.geographic_level }, row.last_updated,
        "Reported BESCOM supply-area value; not scored as Bengaluru city data.", null, "climate");
    }).filter(function (item) { return !!item.source_url; });
  }

  function availablePeriods() {
    var seen = {};
    var values = [];
    // Helper: add a canonical period string once
    var add = function (raw) {
      var key = String(raw == null ? "" : raw).trim();
      if (!key || seen[key]) return;
      seen[key] = true;
      values.push(key);
    };
    var air = DATA.air || {}, carbon = DATA.carbon || {}, water = DATA.water || {};

    // Air quality: dataset year (e.g. "2016-17")
    if (air.year) add(air.year);
    // Live AQI period label (if scoring-eligible)
    if (air.live && air.live.scoring_eligible && air.live.period_label) add(air.live.period_label);

    // Water quality: use the canonical "2020-21" key (source says "Apr 2020 - Mar 2021")
    if (water.period || water.station_months_monitored) add("2020-21");

    // Carbon: each year that has a Total entry with a value
    (carbon.series || []).filter(function (row) {
      return row.sector === "Total" && isNumber(row.mmt_co2e);
    }).forEach(function (row) { add(String(row.year)); });

    // Only keep periods that actually yield indicators in any function
    var withData = values.filter(function (p) {
      return airRecords(p).length > 0 || waterRecords(p).length > 0 || carbonRecords(p).length > 0;
    });

    // Sort descending by the first 4-digit year found in the period string
    withData.sort(function (a, b) {
      var ya = Number((a.match(/\d{4}/) || [0])[0]);
      var yb = Number((b.match(/\d{4}/) || [0])[0]);
      return yb - ya || b.localeCompare(a);
    });
    return withData;
  }

  function calculate(period) {
    var indicators = airRecords(period).concat(waterRecords(period), carbonRecords(period), electricityRecords(period));
    var scores = indicators.filter(function (item) { return item.category === "environmental" && isNumber(item.score); })
      .map(function (item) { return item.score; });
    var environmentalScore = scores.length ? scores.reduce(function (sum, value) { return sum + value; }, 0) / scores.length : null;
    var climateHasValues = indicators.some(function (item) { return item.category === "climate"; });
    var categories = {
      environmental: {
        score: environmentalScore,
        status: environmentalScore == null ? "No indicators for this period" : (scores.length + " verified indicators")
      },
      social: { score: null, scoreText: "Pending", status: "Official dataset pending" },
      governance: { score: null, scoreText: "Pending", status: "Official dataset pending" },
      climate: { score: null, scoreText: "Pending", status: climateHasValues ? "Verified inventory (not scored)" : "Data unavailable" }
    };
    return {
      period: period,
      indicators: indicators,
      categories: categories,
      overall: null
    };
  }

  function formatPeriod(p) {
    // "2020-21" → "2020–21"  |  "2016-17" → "2016–17"  |  "2019" → "2019"
    return String(p || "").replace(/(\d{4})-(\d{2,4})/, "$1\u2013$2");
  }

  function render(period) {
    var result = calculate(period);

    // Update the period display (no removed cards to update)
    $("esg-selected-period").textContent = formatPeriod(period) || "No source period available";

    // Indicator sources table
    var table = result.indicators.map(function (item) {
      var sourceLink = (item.source_urls || [item.source_url]).map(function (url, index) {
        var label = index === 0 ? item.source_title || "Official source" : "Benchmark source";
        return '<a href="' + escapeHTML(url) + '" target="_blank" rel="noopener noreferrer">' + escapeHTML(label) + "</a>";
      }).join(" · ");
      var value = escapeHTML(item.value) + (item.unit ? " " + escapeHTML(item.unit) : "");
      if (item.observation_count) value += " (" + escapeHTML(item.observation_count) + ")";
      var details = [item.source_organization, item.location,
        item.retrieved_at ? "Retrieved " + item.retrieved_at : "Retrieval date not recorded"]
        .filter(Boolean).map(escapeHTML).join(" · ");
      if (item.methodology) details += (details ? "<br>" : "") + "Method: " + escapeHTML(item.methodology);
      var score = isNumber(item.score) ? item.score.toFixed(1) + " / 100" : "Not scored";
      return "<tr><th scope=\"row\">" + escapeHTML(item.indicator) + "</th><td>" + value + "</td><td>" +
        escapeHTML(formatPeriod(item.period)) + "</td><td>" + escapeHTML(item.geographic_level || "Not specified") + "</td><td>" + score +
        "</td><td>" + sourceLink + (details ? "<br><small>" + details + "</small>" : "") + "</td></tr>";
    }).join("");
    $("esg-indicator-rows").innerHTML = table || '<tr><td colspan="6">No source records for this period.</td></tr>';

    var statusEl = $("esg-data-status");
    if (statusEl) {
      statusEl.textContent = result.indicators.length
        ? "Showing verified source records for " + formatPeriod(period) + "."
        : "No verified source records are available for this period.";
    }

    console.info("[UrbanPulse ESG] period", period, "indicators", result.indicators.length);
    window.URBANPULSE_ESG_SCORECARD = result;
  }

  function start(data) {
    DATA = data || {};
    var selector = $("esg-year-select"), periods = availablePeriods();
    selector.replaceChildren();
    periods.forEach(function (period) {
      var option = document.createElement("option");
      option.value = period;
      option.textContent = formatPeriod(period);
      selector.appendChild(option);
    });
    selector.disabled = !periods.length;
    if (!periods.length) {
      render("");
      return;
    }
    // Default to the most recent period that has environmental (scored) indicators
    var defaultPeriod = periods[0];
    for (var i = 0; i < periods.length; i++) {
      var indicators = airRecords(periods[i]).concat(waterRecords(periods[i]));
      var hasScoredEnv = indicators.some(function (item) { return item.category === "environmental" && isNumber(item.score); });
      if (hasScoredEnv) { defaultPeriod = periods[i]; break; }
    }
    selector.value = defaultPeriod;
    selector.onchange = function () { render(selector.value); };
    render(selector.value);
  }

  window.URBANPULSE_ESG = { start: start, calculate: calculate, availablePeriods: availablePeriods };

  function initScorecard() {
    var loadData = window.ESG_ENV && window.ESG_ENV.start ? window.ESG_ENV.start() : Promise.resolve({});
    Promise.resolve(loadData).then(start).catch(function (error) {
      console.error("Unable to load ESG source records:", error);
      start({});
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initScorecard);
  } else {
    initScorecard();
  }
})();