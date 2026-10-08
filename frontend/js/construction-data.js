/**
 * UrbanPulse – Construction Data Adapter
 * Tries the API first, falls back to static window.UP_CONSTRUCTION data.
 * Exports window.URBANPULSE_CONSTRUCTION_DATA once resolved.
 */
(function () {
  "use strict";

  function resolveData() {
    var api = window.UrbanPulseAPI;
    if (!api) return Promise.resolve(window.UP_CONSTRUCTION || {});

    return Promise.all([
      api.getConstructionOverview().catch(function () { return null; }),
      api.getConstructionClustering().catch(function () { return null; }),
      api.getTopWards("investment", 15).catch(function () { return null; }),
      api.getCategoryTags().catch(function () { return null; }),
      api.getWardLevelData().catch(function () { return null; })
    ]).then(function (results) {
      var local = window.UP_CONSTRUCTION || {};
      return {
        overview:      (results[0] && results[0].total_work_orders) ? results[0] : local.overview,
        clustering:    (results[1] && results[1].clusters)           ? results[1] : local.clustering,
        top_wards:     (results[2] && results[2].length)             ? results[2] : local.top_wards,
        category_tags: (results[3] && results[3].length)             ? results[3] : local.category_tags,
        ward_histogram: local.ward_histogram
      };
    }).catch(function () { return window.UP_CONSTRUCTION || {}; });
  }

  window.URBANPULSE_CONSTRUCTION_READY = resolveData().then(function (data) {
    window.URBANPULSE_CONSTRUCTION_DATA = data;
    return data;
  });
})();
