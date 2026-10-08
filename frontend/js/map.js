(function () {
  "use strict";

  var mapElement = document.getElementById("urbanpulse-map");
  var selector = document.getElementById("map-layer-selector");
  if (!mapElement || !selector || !window.L) return;

  var map = L.map(mapElement).setView([12.9716, 77.5946], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>',
    maxZoom: 19
  }).addTo(map);

  var mapInfo = {
    healthcare: { title: "Hospitals", icon: "✚", color: "healthcare", selector: "healthcare" },
    parks: { title: "Parks", icon: "🌳", color: "parks", selector: "parks" },
    education: { title: "Schools & Universities", icon: "🏫", color: "education", selector: "education" },
    transport: { title: "Public Transport", icon: "🚌", color: "transport", selector: "transport" },
    utilities: { title: "Water / Utilities", icon: "💧", color: "utilities", selector: "utilities" },
    government: { title: "Government Services", icon: "🏛", color: "government", selector: "government" },
    police: { title: "Police Stations", icon: "🚓", color: "police", selector: "police" }
  };
  var snapshot = {};
  var activeLayer = null;
  var activeCategory = null;
  var requestToken = 0;
  var overpassRequested = false;
  var headerTitle = document.getElementById("map-header-title");
  var headerSource = document.getElementById("map-header-source");
  var floatingPanels = [
    document.getElementById("map-floating-panel"),
    document.getElementById("map-floating-panel-police"),
    document.getElementById("map-floating-panel-construction")
  ];

  function escapeHTML(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
    });
  }

  function firstTag(tags, keys) {
    for (var i = 0; i < keys.length; i += 1) {
      if (tags[keys[i]] != null && String(tags[keys[i]]).trim()) return String(tags[keys[i]]);
    }
    return "";
  }

  function popupRows(feature) {
    var tags = feature.tags || {};
    var category = feature.category;
    var fields = [];
    var add = function (label, keys) {
      var value = firstTag(tags, keys);
      if (value) fields.push([label, value]);
    };

    if (category === "healthcare") {
      add("Type", ["healthcare", "amenity"]);
      add("Specialty", ["healthcare:speciality", "healthcare:specialty"]);
      add("Rating", ["stars", "rating"]);
      add("Timings", ["opening_hours"]);
      add("Phone", ["phone", "contact:phone"]);
      add("Email", ["email", "contact:email"]);
      add("Website", ["website", "contact:website"]);
      add("Emergency", ["emergency"]);
      add("Operator", ["operator"]);
    } else if (category === "parks") {
      add("Type", ["leisure"]);
      add("Opening hours", ["opening_hours"]);
      add("Playground", ["playground"]);
      add("Sports facilities", ["sport"]);
      add("Toilets", ["toilets"]);
      add("Drinking water", ["drinking_water"]);
      add("Pets", ["pets", "dog"]);
      add("Website", ["website"]);
    } else if (category === "education") {
      add("Institution type", ["amenity", "education"]);
      add("Education level", ["isced:level", "level", "grades"]);
      add("Operator", ["operator"]);
      add("Operator type", ["operator:type"]);
      add("Phone", ["phone", "contact:phone"]);
      add("Email", ["email", "contact:email"]);
      add("Website", ["website", "contact:website"]);
      add("Established", ["start_date"]);
    } else if (category === "police") {
      add("Facility type", ["amenity", "police"]);
      add("Police facility", ["police"]);
      add("Operator", ["operator"]);
      add("Phone", ["phone", "contact:phone"]);
      add("Opening hours", ["opening_hours"]);
      add("Website", ["website", "contact:website"]);
    } else if (category === "transport") {
      add("Stop / station type", ["public_transport", "highway", "railway"]);
      add("Network", ["network"]);
      add("Operator", ["operator"]);
      add("Routes", ["route_ref", "route", "ref"]);
      add("Shelter", ["shelter"]);
      add("Covered", ["covered"]);
      add("Bench", ["bench"]);
    } else if (category === "utilities") {
      add("Facility type", ["man_made", "emergency", "amenity", "power"]);
      add("Status", ["status", "operational_status"]);
      add("Operator", ["operator"]);
      add("Capacity", ["capacity"]);
      add("Last checked", ["check_date"]);
      add("Phone", ["phone", "contact:phone"]);
      add("Website", ["website", "contact:website"]);
    } else if (category === "government") {
      add("Department", ["department"]);
      add("Service", ["government", "office", "amenity"]);
      add("Office type", ["office"]);
      add("Operator", ["operator"]);
      add("Opening hours", ["opening_hours"]);
      add("Phone", ["phone", "contact:phone"]);
      add("Email", ["email", "contact:email"]);
      add("Website", ["website", "contact:website"]);
    }

    return fields;
  }

  function fieldValue(label, value) {
    var safeValue = escapeHTML(value);
    if (label === "Website" && /^https?:\/\//i.test(value)) {
      safeValue = '<a href="' + escapeHTML(value) + '" target="_blank" rel="noopener noreferrer">Open website</a>';
    } else if (label === "Phone") {
      safeValue = '<a href="tel:' + escapeHTML(value.replace(/[^+\d]/g, "")) + '">' + safeValue + '</a>';
    } else if (label === "Email" && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      safeValue = '<a href="mailto:' + escapeHTML(value) + '">' + safeValue + '</a>';
    }
    return safeValue;
  }

  function popupHTML(feature) {
    var info = mapInfo[feature.category];
    var title = feature.name || "Unnamed mapped feature";
    var rows = popupRows(feature);
    if (feature.address) rows.push(["Address", feature.address]);
    var table = rows.map(function (row) {
      return '<tr><th scope="row">' + escapeHTML(row[0]) + '</th><td>' + fieldValue(row[0], row[1]) + '</td></tr>';
    }).join("");
    var osmURL = "https://www.openstreetmap.org/" + encodeURIComponent(feature.osmType || "node") + "/" + encodeURIComponent(feature.osmId);
    return '<div class="popup-inner civic-popup"><h4><span aria-hidden="true">' + info.icon + '</span>' + escapeHTML(title) + '</h4>' +
      '<div class="popup-divider"></div><table class="popup-table">' + table + '</table>' +
      '<a class="civic-popup-source" href="' + osmURL + '" target="_blank" rel="noopener noreferrer">OpenStreetMap object</a></div>';
  }

  function normalizeElement(element, category) {
    var tags = element.tags || {};
    var center = element.center || element;
    var latitude = Number(center.lat);
    var longitude = Number(center.lon);
    if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) return null;
    return {
      category: category,
      osmType: element.type,
      osmId: element.id,
      lat: latitude,
      lon: longitude,
      name: tags.name || tags["name:en"] || "",
      address: [tags["addr:housenumber"], tags["addr:street"], tags["addr:suburb"], tags["addr:city"]].filter(Boolean).join(", "),
      tags: tags
    };
  }

  function createLayer(features, category) {
    var info = mapInfo[category];
    var layer = L.featureGroup();
    var icon = L.divIcon({
      className: "civic-marker civic-marker-" + info.color,
      html: '<span aria-hidden="true">' + info.icon + '</span>',
      iconSize: [34, 34],
      iconAnchor: [17, 17],
      popupAnchor: [0, -16]
    });
    features.forEach(function (feature) {
      if (!Number.isFinite(Number(feature.lat)) || !Number.isFinite(Number(feature.lon))) return;
      L.marker([Number(feature.lat), Number(feature.lon)], { icon: icon, title: feature.name || info.title })
        .bindPopup(popupHTML(feature), { maxWidth: 330 })
        .addTo(layer);
    });
    return layer;
  }

  function setLayerHeader(category, count, source) {
    var info = mapInfo[category];
    if (headerTitle) headerTitle.textContent = info.title + " in Bengaluru";
    if (headerSource) headerSource.textContent = source + " · " + count + " mapped locations";
  }

  function hideFloatingPanels() {
    floatingPanels.forEach(function (panel) { if (panel) panel.style.display = "none"; });
  }

  function showLegacyLayer(category) {
    map.closePopup();
    if (activeLayer) map.removeLayer(activeLayer);
    activeLayer = null;
    activeCategory = category;
    hideFloatingPanels();

    if (category === "construction") {
      var constructionPanel = document.getElementById("map-floating-panel-construction");
      if (constructionPanel) constructionPanel.style.display = "block";
      var constructionValues = {
        "construction-panel-orders": "4,729",
        "construction-panel-amount": "₹3,169.06 Cr",
        "construction-panel-wards": "198 / 198 official wards represented",
        "construction-panel-contractors": "1,603",
        "construction-panel-clusters": "2 (K-Means++, K=2)"
      };
      Object.keys(constructionValues).forEach(function (id) {
        var element = document.getElementById(id);
        if (element) element.textContent = constructionValues[id];
      });
      if (headerTitle) headerTitle.textContent = "BBMP 2025-26 Construction Work Orders";
      if (headerSource) headerSource.textContent = "BBMP work-order dataset · no supplied site coordinates or status";
      return;
    }

    var crimePanel = document.getElementById("map-floating-panel");
    if (crimePanel) crimePanel.style.display = "block";
    if (headerTitle) headerTitle.textContent = "Crime & Safety";
    if (headerSource) headerSource.textContent = "No verified area-level incident data supplied; no incident locations shown";
  }

  function displayCategory(category, features, source, zoomToFeatures) {
    map.closePopup();
    if (activeLayer) map.removeLayer(activeLayer);
    activeCategory = category;
    activeLayer = createLayer(features, category).addTo(map);
    setLayerHeader(category, activeLayer.getLayers().length, source);
    hideFloatingPanels();
    if (category === "police") {
      var policePanel = document.getElementById("map-floating-panel-police");
      if (policePanel) policePanel.style.display = "block";
      var count = document.getElementById("police-panel-total");
      var stationCount = document.getElementById("police-panel-stations");
      if (count) count.textContent = String(activeLayer.getLayers().length);
      if (stationCount) stationCount.textContent = String(activeLayer.getLayers().length);
    }
    if (zoomToFeatures && activeLayer.getLayers().length) {
      map.fitBounds(activeLayer.getBounds(), { padding: [32, 32], maxZoom: 15 });
    }
  }

  function overpassQuery() {
    var bounds = "(12.70,77.30,13.20,77.85)";
    var filters = [
      '["amenity"="hospital"]', '["healthcare"="hospital"]',
      '["leisure"="park"]', '["leisure"="playground"]',
      '["amenity"="school"]', '["amenity"="university"]', '["highway"="bus_stop"]',
      '["amenity"="police"]',
      '["public_transport"="platform"]', '["railway"="station"]',
      '["railway"="subway_entrance"]', '["man_made"="water_tower"]',
      '["emergency"="water_tank"]', '["man_made"="wastewater_plant"]',
      '["man_made"="water_works"]', '["amenity"="drinking_water"]',
      '["office"="government"]', '["amenity"="townhall"]',
      '["government"="administrative"]'
    ];
    return "[out:json][timeout:30];(" + filters.map(function (filter) {
      return "nwr" + bounds + filter + ";";
    }).join("") + ");out center tags;";
  }

  function categoryFromTags(tags) {
    if (tags.amenity === "hospital" || tags.healthcare === "hospital") return "healthcare";
    if (tags.leisure === "park" || tags.leisure === "playground") return "parks";
    if (tags.amenity === "school" || tags.amenity === "university") return "education";
    if (tags.amenity === "police") return "police";
    if (tags.highway === "bus_stop" || tags.public_transport === "platform" || tags.railway === "station" || tags.railway === "subway_entrance") return "transport";
    if (tags.man_made === "water_tower" || tags.man_made === "wastewater_plant" || tags.man_made === "water_works" || tags.emergency === "water_tank" || tags.amenity === "drinking_water") return "utilities";
    if (tags.office === "government" || tags.amenity === "townhall" || tags.government === "administrative") return "government";
    return null;
  }

  function refreshFromOverpass() {
    if (overpassRequested) return;
    overpassRequested = true;
    var query = overpassQuery();
    var controller = window.AbortController ? new AbortController() : null;
    var timeout = controller ? window.setTimeout(function () { controller.abort(); }, 28000) : null;
    return fetch("https://overpass-api.de/api/interpreter", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
      body: "data=" + encodeURIComponent(query),
      signal: controller ? controller.signal : undefined
    }).then(function (response) {
      if (!response.ok) throw new Error("Overpass HTTP " + response.status);
      return response.json();
    }).then(function (data) {
      var fresh = {};
      (data.elements || []).forEach(function (element) {
        var category = categoryFromTags(element.tags || {});
        if (!category) return;
        var feature = normalizeElement(element, category);
        if (!feature) return;
        if (!fresh[category]) fresh[category] = [];
        fresh[category].push(feature);
      });
      Object.keys(fresh).forEach(function (category) {
        if (fresh[category].length) snapshot[category] = fresh[category];
      });
      if (mapInfo[activeCategory] && snapshot[activeCategory] && snapshot[activeCategory].length) {
        displayCategory(activeCategory, snapshot[activeCategory], "Live OpenStreetMap / Overpass", false);
      }
    }).catch(function () {
      // Keep the bundled, attributed OSM snapshot visible when the live API is unavailable.
    }).then(function () {
      if (timeout) window.clearTimeout(timeout);
    });
  }

  function selectLayer() {
    var value = selector.value;
    requestToken += 1;
    if (value === "construction" || value === "crime") {
      showLegacyLayer(value);
      return;
    }
    var category = mapInfo[value] ? value : null;
    if (!category) return;
    var features = snapshot[category] || [];
    displayCategory(category, features, "OpenStreetMap contributors (snapshot 2026-10-02)", true);
    refreshFromOverpass();
  }

  fetch("data/civic-map.json", { cache: "no-store" }).then(function (response) {
    if (!response.ok) throw new Error("OSM snapshot HTTP " + response.status);
    return response.json();
  }).then(function (data) {
    data.features.forEach(function (feature) {
      if (!snapshot[feature.category]) snapshot[feature.category] = [];
      snapshot[feature.category].push(feature);
    });
    selector.addEventListener("change", selectLayer);
    if (selector.value) selectLayer();
  }).catch(function () {
    if (headerSource) headerSource.textContent = "OSM snapshot could not be loaded; serve the project over HTTP";
    selector.addEventListener("change", selectLayer);
  });

  window.setTimeout(function () { map.invalidateSize(); }, 0);
})();
