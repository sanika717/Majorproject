/**
 * UrbanPulse – Construction Data Adapter
 * Fetches from the FastAPI backend API and normalizes data for construction charts.
 * Falls back to static window.UP_CONSTRUCTION if backend is offline.
 * Exports window.URBANPULSE_CONSTRUCTION_DATA and window.URBANPULSE_CONSTRUCTION_READY.
 */
(function () {
  "use strict";

  function normalizeOverview(apiOverview, localOverview) {
    var loc = localOverview || {};
    if (!apiOverview) return loc;
    var tot = apiOverview.total_amount != null ? apiOverview.total_amount : (loc.total_amount_cr ? loc.total_amount_cr * 1e7 : 0);
    var net = apiOverview.total_net_expenditure != null ? apiOverview.total_net_expenditure : (loc.net_expenditure_cr ? loc.net_expenditure_cr * 1e7 : 0);
    var ded = apiOverview.total_deduction != null ? apiOverview.total_deduction : (loc.total_deductions_cr ? loc.total_deductions_cr * 1e7 : 0);
    var orders = apiOverview.total_work_orders || loc.total_work_orders || 4729;

    return {
      total_work_orders: orders,
      total_amount_cr: apiOverview.total_amount_cr != null ? apiOverview.total_amount_cr : +(tot / 1e7).toFixed(2),
      net_expenditure_cr: apiOverview.net_expenditure_cr != null ? apiOverview.net_expenditure_cr : +(net / 1e7).toFixed(2),
      total_deductions_cr: apiOverview.total_deductions_cr != null ? apiOverview.total_deductions_cr : +(ded / 1e7).toFixed(2),
      ward_coverage: apiOverview.official_numbered_wards_present || loc.ward_coverage || 198,
      total_wards: apiOverview.official_wards_total || loc.total_wards || 198,
      distinct_ward_values: apiOverview.distinct_ward_values || loc.distinct_ward_values || 209,
      unique_contractors: apiOverview.unique_contractors || loc.unique_contractors || 1603,
      avg_deduction_rate_pct: apiOverview.avg_deduction_rate_pct != null ? apiOverview.avg_deduction_rate_pct : loc.avg_deduction_rate_pct || 10.08,
      non_standard_ward_codes: apiOverview.non_standard_ward_codes_present != null ? apiOverview.non_standard_ward_codes_present : loc.non_standard_ward_codes || 11,
      avg_amount_per_order_lakh: orders ? +((tot / orders) / 1e5).toFixed(2) : loc.avg_amount_per_order_lakh || 67.01
    };
  }

  function normalizeClustering(apiClustering, localClustering) {
    var loc = localClustering || {};
    if (!apiClustering || !apiClustering.clusters || !apiClustering.clusters.length) return loc;
    return {
      k: apiClustering.chosen_k || apiClustering.k || loc.k || 2,
      silhouette_score: apiClustering.silhouette_score != null ? apiClustering.silhouette_score : (apiClustering.silhouette_by_k ? apiClustering.silhouette_by_k["2"] : (loc.silhouette_score || 0.3919)),
      clusters: apiClustering.clusters.map(function (c) {
        var label = c.label || c.cluster_name || ("Cluster " + c.cluster);
        var wards = c.wards != null ? c.wards : (c.ward_count != null ? c.ward_count : 0);
        var avg_orders = c.avg_orders != null ? c.avg_orders : (c.avg_work_orders != null ? +Number(c.avg_work_orders).toFixed(1) : 0);
        var avg_amt_cr = c.avg_amount_cr != null ? c.avg_amount_cr : (c.avg_total_amount ? +(c.avg_total_amount / 1e7).toFixed(2) : 0);
        var avg_contractors = c.avg_contractors != null ? +Number(c.avg_contractors).toFixed(1) : 0;
        return {
          label: label,
          wards: wards,
          avg_orders: avg_orders,
          avg_amount_cr: avg_amt_cr,
          avg_contractors: avg_contractors
        };
      })
    };
  }

  function normalizeWardsList(apiWards) {
    if (!apiWards || !apiWards.length) return [];
    return apiWards.map(function (w) {
      var wStr = String(w.ward || "").trim();
      var isNum = /^\d+$/.test(wStr);
      var wName = isNum ? ("Ward " + wStr) : (wStr ? (wStr + " (Non-standard code)") : "Data unavailable");
      var cl = w.cluster_name || (w.cluster === 0 || w.cluster === "0" || w.cluster === "High" ? "High Development" : "Low Development");
      if (cl.indexOf("High") >= 0) cl = "High Development";
      else if (cl.indexOf("Low") >= 0) cl = "Low Development";

      return {
        ward: wName,
        cluster: cl,
        orders: w.orders != null ? w.orders : (w.total_work_orders != null ? w.total_work_orders : 0),
        amount_cr: w.amount_cr != null ? w.amount_cr : (w.total_amount ? +(w.total_amount / 1e7).toFixed(2) : 0),
        net_cr: w.net_cr != null ? w.net_cr : (w.total_net_expenditure ? +(w.total_net_expenditure / 1e7).toFixed(2) : 0),
        contractors: w.contractors != null ? w.contractors : (w.unique_contractors != null ? w.unique_contractors : 0)
      };
    });
  }

  function normalizeCategoryTags(apiTags, localTags) {
    var loc = localTags || [];
    if (!apiTags) return loc;
    if (Array.isArray(apiTags) && apiTags.length) return apiTags;
    if (typeof apiTags === "object") {
      var map = {
        road_projects: "Road Works",
        development_projects: "Development",
        drain_projects: "Drain / SWD",
        maintenance_projects: "Maintenance",
        water_projects: "Water Works"
      };
      var out = [];
      Object.keys(map).forEach(function (k) {
        if (apiTags[k] != null) {
          out.push({ category: map[k], count: apiTags[k] });
        }
      });
      if (out.length) {
        return out.sort(function (a, b) { return b.count - a.count; });
      }
    }
    return loc;
  }

  function computeWardHistogram(wardsList) {
    if (!wardsList || !wardsList.length) return null;
    var bins = [
      { bin: "1–10 orders",  count: 0 },
      { bin: "11–20 orders", count: 0 },
      { bin: "21–30 orders", count: 0 },
      { bin: "31–40 orders", count: 0 },
      { bin: "41–50 orders", count: 0 },
      { bin: "51+ orders",   count: 0 }
    ];
    wardsList.forEach(function (w) {
      var c = Number(w.total_work_orders != null ? w.total_work_orders : (w.orders || 0));
      if (c <= 10) bins[0].count++;
      else if (c <= 20) bins[1].count++;
      else if (c <= 30) bins[2].count++;
      else if (c <= 40) bins[3].count++;
      else if (c <= 50) bins[4].count++;
      else bins[5].count++;
    });
    return bins;
  }

  function fetchJSON(url) {
    return fetch(url, { cache: "no-store" }).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    });
  }

  function resolveData() {
    var api = window.UrbanPulseAPI;
    var local = window.UP_CONSTRUCTION || {};

    // 1. Try full-data endpoint first (fast, comprehensive, atomic)
    if (api && typeof api.getFullConstructionData === "function") {
      return api.getFullConstructionData().then(function (full) {
        if (!full || !full.overview) throw new Error("Incomplete API full data");
        var hist = computeWardHistogram(full.ward_level_data) || local.ward_histogram || [];
        return {
          overview:                 normalizeOverview(full.overview, local.overview),
          clustering:               normalizeClustering(full.clustering, local.clustering),
          top_wards:                normalizeWardsList(full.top_wards_by_investment || []),
          top_wards_by_investment:  normalizeWardsList(full.top_wards_by_investment || []),
          top_wards_by_work_orders:  normalizeWardsList(full.top_wards_by_work_orders || []),
          category_tags:            normalizeCategoryTags(full.category_tags, local.category_tags),
          ward_histogram:           hist,
          ward_level_data:          full.ward_level_data || []
        };
      }).catch(function (err) {
        console.warn("[ConstructionData] Full data API failed, falling back to static/individual endpoints:", err);
        return fallbackLoading();
      });
    }

    return fallbackLoading();

    function fallbackLoading() {
      // Try static JSON bundled in frontend/data/construction/
      return fetchJSON("data/construction/construction_data.json").then(function (staticData) {
        var hist = computeWardHistogram(staticData.ward_level_data) || local.ward_histogram || [];
        return {
          overview:                 normalizeOverview(staticData.overview, local.overview),
          clustering:               normalizeClustering(staticData.clustering, local.clustering),
          top_wards:                normalizeWardsList(staticData.top_wards_by_investment || []),
          top_wards_by_investment:  normalizeWardsList(staticData.top_wards_by_investment || []),
          top_wards_by_work_orders:  normalizeWardsList(staticData.top_wards_by_work_orders || []),
          category_tags:            normalizeCategoryTags(staticData.category_tags, local.category_tags),
          ward_histogram:           hist,
          ward_level_data:          staticData.ward_level_data || []
        };
      }).catch(function () {
        return {
          overview:                 local.overview,
          clustering:               local.clustering,
          top_wards:                local.top_wards || [],
          top_wards_by_investment:  local.top_wards || [],
          top_wards_by_work_orders:  local.top_wards_by_work_orders || local.top_wards || [],
          category_tags:            local.category_tags || [],
          ward_histogram:           local.ward_histogram || [],
          ward_level_data:          []
        };
      });
    }
  }

  window.URBANPULSE_CONSTRUCTION_READY = resolveData().then(function (data) {
    window.URBANPULSE_CONSTRUCTION_DATA = data;
    return data;
  });
})();
