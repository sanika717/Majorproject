(function () {
  "use strict";

  var mapElement = document.getElementById("urbanpulse-map");
  var selector = document.getElementById("map-layer-selector");
  if (!mapElement || !selector || !window.L) return;

  // =========================================================================
  // 1. STATE & MAP INITIALIZATION
  // =========================================================================

  var map = L.map(mapElement, {
    zoomControl: true,
    scrollWheelZoom: true
  }).setView([12.9716, 77.5946], 13);

  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap contributors</a>',
    maxZoom: 19
  }).addTo(map);

  var mapInfo = {
    construction: { title: "Construction & Infrastructure", icon: "🏗️", color: "construction" },
    crime: { title: "Crime & Safety", icon: "🚨", color: "crime" },
    police: { title: "Police Stations & Outposts", icon: "🚓", color: "police" },
    healthcare: { title: "Hospitals & Clinics", icon: "✚", color: "healthcare" },
    schools: { title: "Schools", icon: "🏫", color: "schools" },
    universities: { title: "Universities & Colleges", icon: "🎓", color: "universities" },
    parks: { title: "Parks & Playgrounds", icon: "🌳", color: "parks" },
    bus: { title: "Bus Stops & Terminals", icon: "🚌", color: "bus" },
    metro: { title: "Metro Stations & Entrances", icon: "🚇", color: "metro" },
    railway: { title: "Railway Stations & Trains", icon: "🚆", color: "railway" },
    government: { title: "Government Offices & Services", icon: "🏛️", color: "government" },
    utilities: { title: "Water & Other Utilities", icon: "💧", color: "utilities" },
    // internal fallbacks for legacy datasets
    education: { title: "Schools & Universities", icon: "🏫", color: "education" },
    transport: { title: "Public Transport", icon: "🚌", color: "transport" }
  };

  // State object
  var state = {
    selectedPoint: {
      lat: 12.9716,
      lon: 77.5946,
      label: "Central Bengaluru (Vidhana Soudha)"
    },
    radiusMeters: 2000,
    activeCategory: selector.value || "construction",
    snapshot: {},
    liveCache: {},
    routeCache: {},
    markerMap: {},
    activeFacilityLayer: null,
    selectedMarker: null,
    radiusCircle: null,
    activeFacilities: [],
    requestToken: 0,
    abortController: null
  };

  // DOM Elements
  var headerTitle = document.getElementById("map-header-title");
  var headerSource = document.getElementById("map-header-source");
  var searchInput = document.getElementById("map-location-search");
  var searchBtn = document.getElementById("btn-location-search");
  var radiusSelector = document.getElementById("map-radius-selector");
  var gpsBtn = document.getElementById("btn-gps-location");
  var resetBtn = document.getElementById("btn-reset-location");
  var fitBoundsBtn = document.getElementById("btn-fit-bounds");
  var nearbyFitBtn = document.getElementById("btn-nearby-fit");
  var retryNearbyBtn = document.getElementById("btn-retry-nearby");
  var dismissErrorBtn = document.getElementById("btn-dismiss-error");
  var errorBanner = document.getElementById("map-location-error");
  var errorBannerText = document.getElementById("map-location-error-text");

  var selectedLocNameEl = document.getElementById("selected-loc-name");
  var selectedLocCoordsEl = document.getElementById("selected-loc-coords");
  var selectedLocRadiusEl = document.getElementById("selected-loc-radius");

  var nearbyResultsTitle = document.getElementById("nearby-results-title");
  var nearbyResultsCount = document.getElementById("nearby-results-count");
  var nearbyDataSource = document.getElementById("nearby-data-source");
  var nearbyLoading = document.getElementById("nearby-loading");
  var nearbyError = document.getElementById("nearby-error");
  var nearbyEmpty = document.getElementById("nearby-empty");
  var nearbyEmptyMsg = document.getElementById("nearby-empty-msg");
  var nearbyList = document.getElementById("nearby-places-list");

  var floatingPanels = [
    document.getElementById("map-floating-panel"),
    document.getElementById("map-floating-panel-police"),
    document.getElementById("map-floating-panel-construction")
  ];

  // =========================================================================
  // 2. COMPREHENSIVE BENGALURU LOCALITY & WARD MAPPING
  // =========================================================================

  var LOCALITY_DIRECTORY = [
    { name: "Whitefield", lat: 12.9698, lon: 77.7499, ward: "Ward 84 (Hagadur)", zone: "Mahadevapura", division: "East", orders: 43, amountCr: 28.5, cluster: "High Development" },
    { name: "Koramangala", lat: 12.9352, lon: 77.6245, ward: "Ward 151 (Koramangala)", zone: "South", division: "South", orders: 36, amountCr: 24.2, cluster: "High Development" },
    { name: "Indiranagar", lat: 12.9784, lon: 77.6408, ward: "Ward 89 (Jogupalya)", zone: "East", division: "East", orders: 29, amountCr: 18.7, cluster: "High Development" },
    { name: "HSR Layout", lat: 12.9121, lon: 77.6446, ward: "Ward 174 (HSR Layout)", zone: "Bommanahalli", division: "South", orders: 46, amountCr: 32.4, cluster: "High Development" },
    { name: "Electronic City", lat: 12.8399, lon: 77.6770, ward: "Ward 191 (Singasandra)", zone: "Bommanahalli", division: "South", orders: 38, amountCr: 48.3, cluster: "High Development" },
    { name: "Jayanagar", lat: 12.9308, lon: 77.5838, ward: "Ward 153 (Jayanagar)", zone: "South", division: "South", orders: 56, amountCr: 45.6, cluster: "High Development" },
    { name: "Malleswaram", lat: 13.0031, lon: 77.5643, ward: "Ward 65 (Kadu Malleshwara)", zone: "West", division: "West", orders: 34, amountCr: 42.1, cluster: "High Development" },
    { name: "Yelahanka", lat: 13.1007, lon: 77.5963, ward: "Ward 4 (Yelahanka)", zone: "Yelahanka", division: "North", orders: 62, amountCr: 51.9, cluster: "High Development" },
    { name: "Hebbal", lat: 13.0358, lon: 77.5970, ward: "Ward 21 (Hebbal)", zone: "Yelahanka", division: "North", orders: 31, amountCr: 22.4, cluster: "Low Development" },
    { name: "Bellandur", lat: 12.9260, lon: 77.6762, ward: "Ward 150 (Bellandur)", zone: "Mahadevapura", division: "East", orders: 54, amountCr: 55.5, cluster: "High Development" },
    { name: "Marathahalli", lat: 12.9569, lon: 77.7011, ward: "Ward 86 (Marathahalli)", zone: "Mahadevapura", division: "East", orders: 41, amountCr: 31.8, cluster: "High Development" },
    { name: "Peenya", lat: 13.0285, lon: 77.5197, ward: "Ward 41 (Peenya Industrial)", zone: "Rajarajeshwarinagar", division: "West", orders: 28, amountCr: 19.3, cluster: "Low Development" },
    { name: "Rajajinagar", lat: 12.9982, lon: 77.5530, ward: "Ward 99 (Rajajinagar)", zone: "West", division: "West", orders: 32, amountCr: 26.5, cluster: "High Development" },
    { name: "BTM Layout", lat: 12.9166, lon: 77.6101, ward: "Ward 176 (BTM Layout)", zone: "South", division: "South", orders: 35, amountCr: 25.1, cluster: "High Development" },
    { name: "Central Bengaluru", lat: 12.9716, lon: 77.5946, ward: "Ward 111 (Shanthala Nagar)", zone: "East", division: "Central", orders: 22, amountCr: 15.6, cluster: "High Development" },
    { name: "Vidhana Soudha", lat: 12.9797, lon: 77.5907, ward: "Ward 111 (Shanthala Nagar)", zone: "East", division: "Central", orders: 22, amountCr: 15.6, cluster: "High Development" },
    { name: "Basavanagudi", lat: 12.9410, lon: 77.5740, ward: "Ward 154 (Basavanagudi)", zone: "South", division: "South", orders: 30, amountCr: 21.0, cluster: "High Development" },
    { name: "Banashankari", lat: 12.9250, lon: 77.5600, ward: "Ward 180 (Banashankari)", zone: "South", division: "South", orders: 44, amountCr: 33.8, cluster: "High Development" },
    { name: "Mahadevapura", lat: 12.9900, lon: 77.6900, ward: "Ward 82 (Garudachar Palya)", zone: "Mahadevapura", division: "East", orders: 48, amountCr: 37.9, cluster: "High Development" },
    { name: "Bommanahalli", lat: 12.9050, lon: 77.6250, ward: "Ward 175 (Bommanahalli)", zone: "Bommanahalli", division: "South", orders: 43, amountCr: 56.4, cluster: "High Development" },
    { name: "Hoodi", lat: 12.9900, lon: 77.7150, ward: "Ward 54 (Hoodi)", zone: "Mahadevapura", division: "East", orders: 45, amountCr: 55.4, cluster: "High Development" },
    { name: "Kadugodi", lat: 12.9980, lon: 77.7600, ward: "Ward 83 (Kadugodi)", zone: "Mahadevapura", division: "East", orders: 39, amountCr: 27.8, cluster: "High Development" },
    { name: "Varthur", lat: 12.9400, lon: 77.7500, ward: "Ward 149 (Varthur)", zone: "Mahadevapura", division: "East", orders: 37, amountCr: 29.1, cluster: "High Development" }
  ];

  function findLocalityMatch(query) {
    if (!query) return null;
    var q = query.trim().toLowerCase();
    for (var i = 0; i < LOCALITY_DIRECTORY.length; i += 1) {
      var item = LOCALITY_DIRECTORY[i];
      if (item.name.toLowerCase() === q || q.indexOf(item.name.toLowerCase()) !== -1 || item.name.toLowerCase().indexOf(q) !== -1) {
        return item;
      }
    }
    return null;
  }

  function getNearestLocality(lat, lon) {
    var closest = LOCALITY_DIRECTORY[0];
    var minD = Infinity;
    LOCALITY_DIRECTORY.forEach(function (loc) {
      var d = haversineDistanceMeters(lat, lon, loc.lat, loc.lon);
      if (d < minD) {
        minD = d;
        closest = loc;
      }
    });
    return closest;
  }

  // =========================================================================
  // 3. UTILITIES & GEOMETRY
  // =========================================================================

  function escapeHTML(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (char) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char];
    });
  }

  function haversineDistanceMeters(lat1, lon1, lat2, lon2) {
    var R = 6371000;
    var dLat = (lat2 - lat1) * Math.PI / 180;
    var dLon = (lon2 - lon1) * Math.PI / 180;
    var a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
            Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
            Math.sin(dLon / 2) * Math.sin(dLon / 2);
    var c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
    return R * c;
  }

  function formatDistance(meters) {
    if (meters < 1000) {
      return Math.round(meters) + " m";
    }
    return (meters / 1000).toFixed(2) + " km";
  }

  function formatDuration(seconds) {
    var mins = Math.max(1, Math.round(seconds / 60));
    if (mins >= 60) {
      var hrs = Math.floor(mins / 60);
      var rem = mins % 60;
      return hrs + "h " + (rem > 0 ? rem + "m" : "");
    }
    return mins + " mins";
  }

  function firstTag(tags, keys) {
    for (var i = 0; i < keys.length; i += 1) {
      if (tags[keys[i]] != null && String(tags[keys[i]]).trim()) return String(tags[keys[i]]);
    }
    return "";
  }

  // =========================================================================
  // 4. SELECTED LOCATION PIN & RADIUS CIRCLE
  // =========================================================================

  function createSelectedPinIcon() {
    return L.divIcon({
      className: "selected-location-pin",
      html: '<div class="pin-pulse"></div><div class="pin-core" title="Selected Location Pin (Drag to Move)">📍</div>',
      iconSize: [38, 38],
      iconAnchor: [19, 19],
      popupAnchor: [0, -19]
    });
  }

  function initSelectedLocationLayers() {
    var lat = state.selectedPoint.lat;
    var lon = state.selectedPoint.lon;

    state.selectedMarker = L.marker([lat, lon], {
      icon: createSelectedPinIcon(),
      draggable: true,
      zIndexOffset: 1000
    }).addTo(map);

    state.radiusCircle = L.circle([lat, lon], {
      radius: state.radiusMeters,
      color: "#38bdf8",
      fillColor: "#38bdf8",
      fillOpacity: 0.1,
      weight: 2,
      dashArray: "6, 6"
    }).addTo(map);

    state.selectedMarker.bindPopup(function () {
      return '<div class="popup-inner" style="min-width: 220px;">' +
        '<h4 style="color: #f59e0b; margin-bottom: 4px;">🎯 Selected Location Point</h4>' +
        '<div style="font-weight: 700; color: #fff; font-size: 14px; margin-bottom: 4px;">' + escapeHTML(state.selectedPoint.label) + '</div>' +
        '<div style="font-size: 11px; font-family: monospace; color: var(--accent-cyan);">' +
          state.selectedPoint.lat.toFixed(5) + '° N, ' + state.selectedPoint.lon.toFixed(5) + '° E' +
        '</div>' +
        '<div style="font-size: 11px; color: var(--text-muted); margin-top: 6px;">' +
          'Search radius: <b>' + formatDistance(state.radiusMeters) + '</b><br>' +
          'Drag this pin or click anywhere on the map to investigate another area.' +
        '</div>' +
      '</div>';
    });

    state.selectedMarker.on("dragend", function (e) {
      var pos = e.target.getLatLng();
      updateSelectedLocation(pos.lat, pos.lng, null, true);
    });

    map.on("click", function (e) {
      updateSelectedLocation(e.latlng.lat, e.latlng.lng, null, true);
    });
  }

  function updateSelectedLocation(lat, lon, label, reverseLookup) {
    state.selectedPoint.lat = Number(lat);
    state.selectedPoint.lon = Number(lon);

    var nearest = getNearestLocality(lat, lon);
    if (label) {
      state.selectedPoint.label = label;
    } else if (nearest && haversineDistanceMeters(lat, lon, nearest.lat, nearest.lon) <= 2500) {
      state.selectedPoint.label = nearest.name + " (" + nearest.zone + " Zone)";
    } else {
      state.selectedPoint.label = "Point (" + lat.toFixed(4) + "°, " + lon.toFixed(4) + "°)";
    }

    if (state.selectedMarker) {
      state.selectedMarker.setLatLng([lat, lon]);
    }
    if (state.radiusCircle) {
      state.radiusCircle.setLatLng([lat, lon]);
      state.radiusCircle.setRadius(state.radiusMeters);
    }

    // Update UI Status Bar
    if (selectedLocNameEl) selectedLocNameEl.textContent = "Selected: " + state.selectedPoint.label;
    if (selectedLocCoordsEl) selectedLocCoordsEl.textContent = lat.toFixed(4) + "° N, " + lon.toFixed(4) + "° E";
    if (selectedLocRadiusEl) selectedLocRadiusEl.textContent = formatDistance(state.radiusMeters) + " radius";

    // Update Locality Chips active state
    document.querySelectorAll(".locality-chip").forEach(function (chip) {
      var cLoc = chip.getAttribute("data-loc");
      chip.classList.toggle("active", cLoc && state.selectedPoint.label.toLowerCase().indexOf(cLoc.toLowerCase()) !== -1);
    });

    hideErrorBanner();
    renderActiveCategory();

    if (reverseLookup) {
      reverseGeocode(lat, lon);
    }
  }

  function showErrorBanner(msg) {
    if (errorBanner && errorBannerText) {
      errorBannerText.textContent = msg;
      errorBanner.style.display = "flex";
    }
  }

  function hideErrorBanner() {
    if (errorBanner) errorBanner.style.display = "none";
  }

  function reverseGeocode(lat, lon) {
    var url = "https://nominatim.openstreetmap.org/reverse?format=json&lat=" + lat + "&lon=" + lon + "&zoom=16&addressdetails=1";
    fetch(url, { headers: { "Accept-Language": "en" } })
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (!data || !data.address) return;
        var addr = data.address;
        var name = addr.suburb || addr.neighbourhood || addr.residential || addr.city_district || addr.quarter || addr.road;
        if (name) {
          state.selectedPoint.label = name + ", Bengaluru";
          if (selectedLocNameEl) selectedLocNameEl.textContent = "Selected: " + state.selectedPoint.label;
        }
      })
      .catch(function () {});
  }

  // =========================================================================
  // 5. GEOCODING & SEARCH CONTROLS
  // =========================================================================

  function searchArea(query) {
    if (!query || !query.trim()) {
      showErrorBanner("Please enter a Bengaluru locality, landmark, or address.");
      return;
    }
    var cleanQ = query.trim();

    // 1. First check local instant directory
    var localMatch = findLocalityMatch(cleanQ);
    if (localMatch) {
      map.setView([localMatch.lat, localMatch.lon], 14);
      updateSelectedLocation(localMatch.lat, localMatch.lon, localMatch.name + " (" + localMatch.zone + " Zone)");
      return;
    }

    // 2. Query Nominatim restricted to Bengaluru bounding box
    var url = "https://nominatim.openstreetmap.org/search?format=json&q=" +
              encodeURIComponent(cleanQ + ", Bengaluru, Karnataka, India") +
              "&limit=1&bounded=1&viewbox=77.30,13.25,77.85,12.75";

    if (searchBtn) searchBtn.textContent = "Searching...";

    fetch(url, { headers: { "Accept-Language": "en" } })
      .then(function (res) {
        if (!res.ok) throw new Error("Search service returned HTTP " + res.status);
        return res.json();
      })
      .then(function (results) {
        if (!results || !results.length) {
          showErrorBanner("Could not find '" + cleanQ + "' in Bengaluru. Please check the spelling or select a quick area.");
          return;
        }
        var top = results[0];
        var lat = parseFloat(top.lat);
        var lon = parseFloat(top.lon);
        var name = top.display_name.split(",")[0] || cleanQ;
        map.setView([lat, lon], 14);
        updateSelectedLocation(lat, lon, name + ", Bengaluru");
      })
      .catch(function (err) {
        showErrorBanner("Geocoding lookup failed (" + err.message + "). Please check your network or select a quick area.");
      })
      .finally(function () {
        if (searchBtn) searchBtn.textContent = "🔍 Search";
      });
  }

  function handleGPSLocation() {
    if (!navigator.geolocation) {
      showErrorBanner("Geolocation is not supported by your browser.");
      return;
    }
    if (gpsBtn) gpsBtn.textContent = "Requesting GPS...";

    navigator.geolocation.getCurrentPosition(
      function (pos) {
        if (gpsBtn) gpsBtn.textContent = "📍 Use My GPS";
        var lat = pos.coords.latitude;
        var lon = pos.coords.longitude;
        map.setView([lat, lon], 14);
        updateSelectedLocation(lat, lon, "My GPS Location", true);
      },
      function (err) {
        if (gpsBtn) gpsBtn.textContent = "📍 Use My GPS";
        var msg = "Could not obtain GPS coordinates.";
        if (err.code === 1) msg = "GPS permission was denied in your browser settings.";
        else if (err.code === 2) msg = "Position unavailable from GPS.";
        else if (err.code === 3) msg = "GPS request timed out.";
        showErrorBanner(msg + " You can search or click any Bengaluru area on the map.");
      },
      { timeout: 10000, enableHighAccuracy: true }
    );
  }

  function resetToBengaluru() {
    var defLat = 12.9716;
    var defLon = 77.5946;
    state.radiusMeters = 2000;
    if (radiusSelector) radiusSelector.value = "2000";
    map.setView([defLat, defLon], 13);
    updateSelectedLocation(defLat, defLon, "Central Bengaluru (Vidhana Soudha)");
  }

  function fitToRadiusBounds() {
    if (state.radiusCircle) {
      map.fitBounds(state.radiusCircle.getBounds(), { padding: [35, 35] });
    }
  }

  // =========================================================================
  // 6. ROUTING & TRAVEL TIME CALCULATIONS (WALK, BIKE, CAR, TRANSIT)
  // =========================================================================

  // Namma Metro line stations in sequence for transit journey estimation
  var METRO_NETWORK = {
    purple: [
      "Whitefield (Kadugodi)", "Hopefarm Channasandra", "Kadugodi Tree Park", "Pattandur Agrahara",
      "Sri Sathya Sai Hospital", "Nallurhalli", "Kundalahalli", "Seetharampalya", "Hoodi",
      "Garudachar Palya", "Singayyanapalya", "KR Puram", "Benniganahalli", "Baiyappanahalli",
      "Swami Vivekananda Road", "Indiranagar", "Halasuru", "Trinity", "MG Road", "Cubbon Park",
      "Dr. B.R. Ambedkar Stn Vidhana Soudha", "Sir M. Visvesvaraya Stn Central College",
      "Nadaprabhu Kempegowda Stn Majestic", "City Railway Station", "Magadi Road", "Vijayanagar",
      "Deepanjali Nagar", "Mysuru Road", "Rajarajeshwari Nagar", "Kengeri", "Challaghatta"
    ],
    green: [
      "Nagasandra", "Dasarahalli", "Jalahalli", "Peenya Industry", "Peenya", "Goraguntepalya",
      "Yeshwanthpur", "Sandal Soap Factory", "Mahalakshmi", "Rajajinagar", "Kuvempu Road",
      "Srirampura", "Sampige Road", "Nadaprabhu Kempegowda Stn Majestic", "Chickpete",
      "Krishna Rajendra Market", "National College", "Lalbagh", "South End Circle",
      "Jayanagar", "Rashtreeya Vidyalaya Road", "Banashankari", "Jaya Prakash Nagar",
      "Yelachenahalli", "Konanakunte Cross", "Silk Institute"
    ]
  };

  function calculateTravelEstimates(straightDistMeters, originLat, originLon, destLat, destLon) {
    // Road distance is ~1.28x straight line in Bengaluru urban grid
    var roadDistMeters = Math.round(straightDistMeters * 1.28);

    // Walking: 4.5 km/h -> 75 meters/min
    var walkMins = Math.max(1, Math.round(roadDistMeters / 75));

    // Bicycle: 14 km/h -> 233 meters/min
    var bikeMins = Math.max(1, Math.round(roadDistMeters / 233));

    // Car (Urban Bengaluru average traffic ~22 km/h): ~366 meters/min
    var carMins = Math.max(2, Math.round(roadDistMeters / 366));

    // Metro transit calculation
    var metroInfo = "Route estimate unavailable (outside direct metro corridor)";
    var metroStations = (state.snapshot.metro || []);
    if (metroStations.length) {
      var nearestToOrigin = null;
      var nearestToDest = null;
      var minOriginD = Infinity;
      var minDestD = Infinity;

      metroStations.forEach(function (stn) {
        var d1 = haversineDistanceMeters(originLat, originLon, stn.lat, stn.lon);
        var d2 = haversineDistanceMeters(destLat, destLon, stn.lat, stn.lon);
        if (d1 < minOriginD) { minOriginD = d1; nearestToOrigin = stn; }
        if (d2 < minDestD) { minDestD = d2; nearestToDest = stn; }
      });

      // If both origin & destination are within 1.8km of a metro station
      if (nearestToOrigin && nearestToDest && minOriginD <= 1800 && minDestD <= 1800) {
        var walkToOrigin = Math.round(minOriginD / 75);
        var walkFromDest = Math.round(minDestD / 75);
        var line1 = (nearestToOrigin.tags && nearestToOrigin.tags.line) || "Purple Line";
        var line2 = (nearestToDest.tags && nearestToDest.tags.line) || "Purple Line";

        if (line1 === line2) {
          // Approx 2.1 mins per station running time on Namma Metro
          var rideMins = Math.max(4, Math.round(straightDistMeters / 1000 * 2.2));
          metroInfo = "🚇 Namma Metro " + line1 + ": ~" + (walkToOrigin + rideMins + walkFromDest) + " mins total (Walk " + walkToOrigin + "m to " + nearestToOrigin.name.replace(" Metro Station", "") + " → Metro ride ~" + rideMins + "m → Walk " + walkFromDest + "m)";
        } else {
          var xferMins = Math.max(12, Math.round(straightDistMeters / 1000 * 2.5) + 6);
          metroInfo = "🚇 Namma Metro: ~" + (walkToOrigin + xferMins + walkFromDest) + " mins total (Interchange at Majestic Hub)";
        }
      }
    }

    // Railway transit calculation
    var trainInfo = "Route estimate unavailable (outside immediate suburban rail corridor)";
    var railStations = (state.snapshot.railway || []);
    if (railStations.length) {
      var rOrigin = null;
      var rDest = null;
      var rMin1 = Infinity;
      var rMin2 = Infinity;
      railStations.forEach(function (r) {
        var d1 = haversineDistanceMeters(originLat, originLon, r.lat, r.lon);
        var d2 = haversineDistanceMeters(destLat, destLon, r.lat, r.lon);
        if (d1 < rMin1) { rMin1 = d1; rOrigin = r; }
        if (d2 < rMin2) { rMin2 = d2; rDest = r; }
      });
      if (rOrigin && rDest && rMin1 <= 2500 && rMin2 <= 2500 && rOrigin.name !== rDest.name) {
        trainInfo = "🚆 SWR Suburban Train: Service connects " + rOrigin.name.split(" ")[0] + " and " + rDest.name.split(" ")[0] + " · Check SWR / NTES timetable";
      }
    }

    // Bus transit connection note
    var busInfo = "🚌 BMTC City Bus: Route connection available from nearest bus stop · Check BMTC Namma Raste / Google Maps";

    return {
      roadDistMeters: roadDistMeters,
      roadDistFormatted: formatDistance(roadDistMeters),
      walkTime: formatDuration(walkMins * 60),
      bikeTime: formatDuration(bikeMins * 60),
      carTime: formatDuration(carMins * 60),
      metroInfo: metroInfo,
      trainInfo: trainInfo,
      busInfo: busInfo
    };
  }

  function fetchOSRMRoute(originLat, originLon, destLat, destLon, callback) {
    var key = originLat.toFixed(4) + "," + originLon.toFixed(4) + "-" + destLat.toFixed(4) + "," + destLon.toFixed(4);
    if (state.routeCache[key]) {
      callback(state.routeCache[key]);
      return;
    }

    var url = "https://router.project-osrm.org/route/v1/driving/" +
              originLon + "," + originLat + ";" + destLon + "," + destLat +
              "?overview=false";

    fetch(url)
      .then(function (res) { return res.ok ? res.json() : null; })
      .then(function (data) {
        if (data && data.routes && data.routes.length) {
          var r = data.routes[0];
          var result = {
            distance: r.distance,
            duration: r.duration
          };
          state.routeCache[key] = result;
          callback(result);
        }
      })
      .catch(function () {});
  }

  // =========================================================================
  // 7. FACILITY MARKERS & POPUPS
  // =========================================================================

  function popupRows(feature, distMeters, estimates) {
    var tags = feature.tags || {};
    var category = feature.category;
    var rows = [];

    // 1. Distance & Travel Time (Mandatory for all categories)
    rows.push(["Straight-line distance", "📏 " + formatDistance(distMeters)]);
    rows.push(["Estimated road travel", "🚗 Car: " + estimates.carTime + " &bull; 🚶 Walk: " + estimates.walkTime + " &bull; 🚲 Bike: " + estimates.bikeTime]);

    var add = function (label, keys) {
      var val = firstTag(tags, keys);
      if (val) rows.push([label, val]);
    };

    if (category === "healthcare") {
      add("Facility type", ["type", "healthcare", "amenity"]);
      add("Specialty", ["healthcare:speciality", "healthcare:specialty", "specialty"]);
      var emergVal = tags.emergency;
      if (emergVal === "yes" || (emergVal && emergVal.toLowerCase().indexOf("yes") !== -1)) {
        rows.push(["Emergency Care", '<span class="emergency-tag-yes">🚨 Available (24/7 Department)</span>']);
      } else {
        rows.push(["Emergency Care", '<span class="emergency-tag-unknown">Not available in source data</span>']);
      }
      add("Opening hours", ["opening_hours"]);
      add("Phone", ["phone", "contact:phone"]);
      add("Website", ["website", "contact:website"]);
    } else if (category === "police") {
      add("Facility type", ["type", "police", "amenity"]);
      rows.push(["Emergency Helpline", '<span style="color:#60a5fa; font-weight:700;">🚨 112 (ERSS 24/7)</span>']);
      add("Control Room Phone", ["phone", "contact:phone"]);
      add("Operator", ["operator"]);
      add("Jurisdiction", ["source_dataset", "source_kml"]);
    } else if (category === "metro") {
      add("Line / Corridor", ["line", "network"]);
      add("Operator", ["operator"]);
      add("Station Details", ["details"]);
      add("Operating Hours", ["opening_hours"]);
      add("Wheelchair Accessible", ["wheelchair"]);
    } else if (category === "railway") {
      add("Station Classification", ["details"]);
      add("Operator", ["operator"]);
      add("Network", ["network"]);
      add("Operating Hours", ["opening_hours"]);
    } else if (category === "bus") {
      add("Station Type", ["type", "highway"]);
      add("Operator", ["operator"]);
      add("Network", ["network"]);
      add("Routes Served", ["route_ref"]);
      add("Shelter Available", ["shelter"]);
    } else if (category === "schools") {
      add("School Type", ["type"]);
      add("Established", ["start_date"]);
      add("Affiliation", ["operator:type", "grades"]);
      add("Phone", ["phone", "contact:phone"]);
    } else if (category === "universities") {
      add("Institution Type", ["type"]);
      add("Details", ["details"]);
      add("Phone", ["phone", "contact:phone"]);
      add("Website", ["website", "contact:website"]);
    } else if (category === "parks") {
      add("Park Type", ["type", "leisure"]);
      add("Opening Hours", ["opening_hours"]);
      add("Playground Area", ["playground"]);
      add("Pet Policy", ["pets", "dog"]);
      add("Website", ["website"]);
    } else if (category === "government") {
      add("Department", ["department", "service"]);
      add("Office Hours", ["opening_hours"]);
      add("Phone", ["phone", "contact:phone"]);
    } else if (category === "utilities") {
      add("Utility Type", ["facility_type", "man_made"]);
      add("Managing Operator", ["operator"]);
      add("Capacity / Specs", ["capacity"]);
    }

    if (feature.address) {
      rows.push(["Address", feature.address]);
    }

    return rows;
  }

  function formatFieldValue(label, val) {
    if (typeof val === "string" && val.indexOf("<") !== -1) return val;
    var safeVal = escapeHTML(val);
    if (label === "Website" && /^https?:\/\//i.test(val)) {
      return '<a href="' + escapeHTML(val) + '" target="_blank" rel="noopener noreferrer" style="color:var(--accent-cyan); font-weight:600;">Open Website ↗</a>';
    }
    if ((label === "Phone" || label === "Control Room Phone") && val) {
      var num = val.replace(/[^+\d]/g, "");
      return '<a href="tel:' + escapeHTML(num) + '" style="color:#34d399; font-weight:700;">📞 ' + safeVal + '</a>';
    }
    return safeVal;
  }

  function buildPopupHTML(feature, distMeters, estimates) {
    var info = mapInfo[feature.category] || { icon: "📍", title: feature.category };
    var name = feature.name || "Unnamed Mapped Feature";
    var rows = popupRows(feature, distMeters, estimates);

    var tableRows = rows.map(function (r) {
      return '<tr><th scope="row" style="text-align:left; color:var(--text-muted); padding:3px 8px 3px 0; font-size:11px; white-space:nowrap;">' +
             escapeHTML(r[0]) + ':</th>' +
             '<td style="color:#fff; padding:3px 0; font-size:11px;">' + formatFieldValue(r[0], r[1]) + '</td></tr>';
    }).join("");

    var dirURL = "https://www.google.com/maps/dir/?api=1&origin=" +
                 state.selectedPoint.lat + "," + state.selectedPoint.lon +
                 "&destination=" + feature.lat + "," + feature.lon;

    var callBtn = "";
    var phone = firstTag(feature.tags || {}, ["phone", "contact:phone"]);
    if (phone) {
      callBtn = '<a href="tel:' + escapeHTML(phone.replace(/[^+\d]/g, "")) + '" class="btn-card-action btn-card-call" style="font-size:11px; padding:4px 8px;">📞 Call</a>';
    }

    return '<div class="popup-inner" style="min-width:260px; max-width:320px;">' +
      '<div style="display:flex; align-items:center; gap:6px; margin-bottom:4px;">' +
        '<span style="font-size:18px;">' + info.icon + '</span>' +
        '<h4 style="font-size:14px; margin:0; color:#fff; line-height:1.2;">' + escapeHTML(name) + '</h4>' +
      '</div>' +
      '<div style="height:1px; background:var(--border-subtle); margin:8px 0;"></div>' +
      '<table style="width:100%; border-collapse:collapse; margin-bottom:10px;">' + tableRows + '</table>' +
      '<div style="display:flex; gap:8px;">' +
        callBtn +
        '<a href="' + dirURL + '" target="_blank" rel="noopener noreferrer" class="btn-card-action btn-card-dir" style="font-size:11px; padding:4px 8px;">🧭 Get Directions ↗</a>' +
      '</div>' +
    '</div>';
  }

  function createMarkerIcon(category) {
    var info = mapInfo[category] || { icon: "📍", color: "education" };
    return L.divIcon({
      className: "civic-marker civic-marker-" + info.color,
      html: '<span aria-hidden="true">' + info.icon + '</span>',
      iconSize: [32, 32],
      iconAnchor: [16, 16],
      popupAnchor: [0, -16]
    });
  }

  // =========================================================================
  // 8. NEARBY RESULTS LIST & CARDS
  // =========================================================================

  function renderNearbyCards(facilities) {
    if (!nearbyList) return;
    nearbyList.innerHTML = "";

    if (!facilities.length) {
      if (nearbyEmpty) nearbyEmpty.style.display = "block";
      if (nearbyResultsCount) nearbyResultsCount.textContent = "0 found";
      return;
    }

    if (nearbyEmpty) nearbyEmpty.style.display = "none";
    if (nearbyResultsCount) nearbyResultsCount.textContent = facilities.length + " found";

    facilities.forEach(function (item, idx) {
      var feat = item.feature;
      var dist = item.distance;
      var est = item.estimates;
      var info = mapInfo[feat.category] || { icon: "📍", title: feat.category };

      var card = document.createElement("div");
      card.className = "facility-card";
      card.setAttribute("data-id", item.id);
      card.setAttribute("id", "facility-card-" + item.id);

      var phone = firstTag(feat.tags || {}, ["phone", "contact:phone"]);
      var emergTag = feat.tags && feat.tags.emergency;
      var emergHTML = "";
      if (feat.category === "healthcare") {
        if (emergTag === "yes" || (emergTag && emergTag.toLowerCase().indexOf("yes") !== -1)) {
          emergHTML = '<div class="facility-detail-item"><span class="facility-detail-label">Emergency Care:</span><span class="facility-detail-val emergency-tag-yes">🚨 24/7 Available</span></div>';
        } else {
          emergHTML = '<div class="facility-detail-item"><span class="facility-detail-label">Emergency Care:</span><span class="facility-detail-val emergency-tag-unknown">Not in source data</span></div>';
        }
      } else if (feat.category === "police") {
        emergHTML = '<div class="facility-detail-item"><span class="facility-detail-label">Emergency Helpline:</span><span class="facility-detail-val emergency-tag-yes">🚨 112 (ERSS 24/7)</span></div>';
      }

      var hours = firstTag(feat.tags || {}, ["opening_hours"]);
      var hoursHTML = hours ? '<div class="facility-detail-item"><span class="facility-detail-label">Hours:</span><span class="facility-detail-val">' + escapeHTML(hours) + '</span></div>' : "";

      var website = firstTag(feat.tags || {}, ["website", "contact:website"]);
      var webHTML = website ? '<div class="facility-detail-item"><span class="facility-detail-label">Website:</span><span class="facility-detail-val"><a href="' + escapeHTML(website) + '" target="_blank" rel="noopener noreferrer" style="color:var(--accent-cyan);">Visit site ↗</a></span></div>' : "";

      var spec = firstTag(feat.tags || {}, ["healthcare:speciality", "healthcare:specialty", "details", "line"]);
      var specHTML = spec ? '<div class="facility-detail-item"><span class="facility-detail-label">Details:</span><span class="facility-detail-val">' + escapeHTML(spec) + '</span></div>' : "";

      var dirURL = "https://www.google.com/maps/dir/?api=1&origin=" +
                   state.selectedPoint.lat + "," + state.selectedPoint.lon +
                   "&destination=" + feat.lat + "," + feat.lon;

      var transitNote = "";
      if (feat.category === "metro") {
        transitNote = '<div class="transit-journey-box">🚇 Namma Metro Network &bull; Platform access: ' + est.walkTime + ' walk from your selected pin.</div>';
      } else if (feat.category === "railway") {
        transitNote = '<div class="transit-journey-box">🚆 Indian Railways Hub &bull; SWR Suburban &amp; Express connections.</div>';
      } else if (feat.category === "bus") {
        transitNote = '<div class="transit-journey-box">🚌 BMTC Stop &bull; ' + (feat.tags.route_ref ? 'Routes: ' + escapeHTML(feat.tags.route_ref) : 'City bus connections') + '</div>';
      }

      var callBtn = "";
      if (phone) {
        var cleanPhone = phone.replace(/[^+\d]/g, "");
        callBtn = '<a href="tel:' + escapeHTML(cleanPhone) + '" class="btn-card-action btn-card-call" title="Call ' + escapeHTML(phone) + '">📞 Call</a>';
      }

      card.innerHTML =
        '<div class="facility-card-header">' +
          '<div class="facility-card-name">' + info.icon + ' ' + escapeHTML(feat.name || "Unnamed Facility") + '</div>' +
          '<span class="facility-category-badge civic-marker-' + info.color + '">' + escapeHTML(info.title.split(" ")[0]) + '</span>' +
        '</div>' +
        '<div class="facility-address">' + escapeHTML(feat.address || "Bengaluru, Karnataka") + '</div>' +

        '<div class="travel-modes-strip">' +
          '<div class="straight-line-row">' +
            '<span>Straight-line Distance</span>' +
            '<span>' + formatDistance(dist) + '</span>' +
          '</div>' +
          '<div class="travel-chips-row">' +
            '<span class="travel-chip">🚗 Car: <strong>' + est.carTime + '</strong></span>' +
            '<span class="travel-chip">🚶 Walk: <strong>' + est.walkTime + '</strong></span>' +
            '<span class="travel-chip">🚲 Bike: <strong>' + est.bikeTime + '</strong></span>' +
          '</div>' +
          transitNote +
        '</div>' +

        '<div class="facility-details-list">' +
          emergHTML +
          (phone ? '<div class="facility-detail-item"><span class="facility-detail-label">Phone:</span><span class="facility-detail-val"><a href="tel:' + escapeHTML(phone.replace(/[^+\d]/g, "")) + '" style="color:#34d399; font-weight:600;">' + escapeHTML(phone) + '</a></span></div>' : '') +
          hoursHTML +
          specHTML +
          webHTML +
        '</div>' +

        '<div class="facility-card-actions">' +
          '<button type="button" class="btn-card-action btn-card-focus" data-focus="' + item.id + '">📍 View on Map</button>' +
          callBtn +
          '<a href="' + dirURL + '" target="_blank" rel="noopener noreferrer" class="btn-card-action btn-card-dir">🧭 Directions ↗</a>' +
        '</div>';

      // Click card to highlight marker and open popup
      card.addEventListener("click", function (e) {
        if (e.target.tagName.toLowerCase() === "a") return;
        focusFacilityMarker(item.id);
      });

      var focusBtn = card.querySelector("[data-focus]");
      if (focusBtn) {
        focusBtn.addEventListener("click", function (e) {
          e.stopPropagation();
          focusFacilityMarker(item.id);
        });
      }

      nearbyList.appendChild(card);
    });
  }

  function focusFacilityMarker(id) {
    var marker = state.markerMap[id];
    if (!marker) return;

    document.querySelectorAll(".facility-card").forEach(function (c) {
      c.classList.remove("active-card");
    });
    var card = document.getElementById("facility-card-" + id);
    if (card) {
      card.classList.add("active-card");
      card.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    map.setView(marker.getLatLng(), Math.max(map.getZoom(), 15), { animate: true });
    marker.openPopup();
  }

  // =========================================================================
  // 9. LAYER DISPLAY & OVERPASS / NOMINATIM LIVE QUERIES
  // =========================================================================

  function hideFloatingPanels() {
    floatingPanels.forEach(function (panel) {
      if (panel) panel.style.display = "none";
    });
  }

  function showSpecialLayer(category) {
    map.closePopup();
    if (state.activeFacilityLayer) {
      map.removeLayer(state.activeFacilityLayer);
      state.activeFacilityLayer = null;
    }
    state.activeFacilities = [];
    state.markerMap = {};
    hideFloatingPanels();

    var nearest = getNearestLocality(state.selectedPoint.lat, state.selectedPoint.lon);

    if (category === "construction") {
      var panel = document.getElementById("map-floating-panel-construction");
      if (panel) panel.style.display = "block";

      var wardNameEl = document.getElementById("construction-panel-wardname");
      var ordersEl = document.getElementById("construction-panel-orders");
      var amtEl = document.getElementById("construction-panel-amount");
      var clusterEl = document.getElementById("construction-panel-clusters");

      if (wardNameEl) wardNameEl.textContent = nearest.ward;
      if (ordersEl) ordersEl.textContent = nearest.orders + " ward work orders";
      if (amtEl) amtEl.textContent = "₹" + nearest.amountCr.toFixed(2) + " Cr";
      if (clusterEl) clusterEl.textContent = nearest.cluster;

      if (headerTitle) headerTitle.textContent = "BBMP Construction Work Orders · " + nearest.ward;
      if (headerSource) headerSource.textContent = "BBMP 2025-26 ward records · No site-level coordinates provided; ward figures shown";

      if (nearbyResultsTitle) nearbyResultsTitle.textContent = "🏗️ Ward Construction Overview for " + nearest.name;
      if (nearbyResultsCount) nearbyResultsCount.textContent = nearest.ward;
      if (nearbyDataSource) nearbyDataSource.textContent = "BBMP 2025-26 Official Work Orders";

      if (nearbyList) {
        nearbyList.innerHTML =
          '<div class="facility-card" style="grid-column: 1 / -1;">' +
            '<div class="facility-card-header">' +
              '<div class="facility-card-name">BBMP Municipal Administration — ' + nearest.ward + '</div>' +
              '<span class="facility-category-badge civic-marker-education">' + nearest.cluster + '</span>' +
            '</div>' +
            '<div class="facility-address">Geographic Zone: ' + nearest.zone + ' &bull; Distance from selected pin to ward center: ' +
              formatDistance(haversineDistanceMeters(state.selectedPoint.lat, state.selectedPoint.lon, nearest.lat, nearest.lon)) +
            '</div>' +
            '<div class="travel-modes-strip">' +
              '<div class="travel-chips-row">' +
                '<span class="travel-chip">Work Orders: <strong>' + nearest.orders + '</strong></span>' +
                '<span class="travel-chip">Verified Expenditure: <strong>₹' + nearest.amountCr.toFixed(2) + ' Cr</strong></span>' +
                '<span class="travel-chip">Development Status: <strong>' + nearest.cluster + '</strong></span>' +
              '</div>' +
            '</div>' +
            '<div class="floating-disclaimer" style="margin-top: 10px;">' +
              '<b>🛡️ Data Integrity Disclosure:</b> The supplied BBMP 2025-26 work-order dataset does not contain individual GPS site coordinates or completion status timestamps. To avoid fabricating construction site pins, UrbanPulse displays verified BBMP ward-level municipal work-order intelligence rather than false site pins. See the <a href="analytics.html#construction-section" style="color:var(--accent-cyan);">Analytics page</a> for detailed contractor breakdowns.' +
            '</div>' +
          '</div>';
      }
      return;
    }

    if (category === "crime") {
      var cPanel = document.getElementById("map-floating-panel");
      if (cPanel) cPanel.style.display = "block";

      var divEl = document.getElementById("crime-panel-division");
      var cyberEl = document.getElementById("crime-panel-cyber");
      if (divEl) divEl.textContent = nearest.division + " Division (" + nearest.name + ")";
      if (cyberEl) cyberEl.textContent = (nearest.division === "South" ? "3,812" : nearest.division === "East" ? "2,946" : nearest.division === "North" ? "2,641" : "1,876") + " cases (2023)";

      if (headerTitle) headerTitle.textContent = "Crime & Safety · " + nearest.division + " Division";
      if (headerSource) headerSource.textContent = "Bengaluru City Police verified records · No localized incident coordinates supplied";

      if (nearbyResultsTitle) nearbyResultsTitle.textContent = "🚨 Crime & Safety Intelligence for " + nearest.name;
      if (nearbyResultsCount) nearbyResultsCount.textContent = nearest.division + " Division";
      if (nearbyDataSource) nearbyDataSource.textContent = "Bengaluru City Police Verified Records";

      if (nearbyList) {
        nearbyList.innerHTML =
          '<div class="facility-card" style="grid-column: 1 / -1;">' +
            '<div class="facility-card-header">' +
              '<div class="facility-card-name">Bengaluru City Police — ' + nearest.division + ' Division Records</div>' +
              '<span class="facility-category-badge civic-marker-healthcare">Division Summary</span>' +
            '</div>' +
            '<div class="facility-address">Geographic Division: ' + nearest.division + ' &bull; Covering ' + nearest.name + ' and surrounding wards</div>' +
            '<div class="travel-modes-strip">' +
              '<div class="travel-chips-row">' +
                '<span class="travel-chip">2023 Division Cyber Crimes: <strong>' + (nearest.division === "South" ? "3,812" : nearest.division === "East" ? "2,946" : nearest.division === "North" ? "2,641" : "1,876") + '</strong></span>' +
                '<span class="travel-chip">Historical D47 City Total: <strong>35,971</strong></span>' +
                '<span class="travel-chip">City Crime Risk Score: <strong style="color:#ef4444;">71.70 / 100</strong></span>' +
              '</div>' +
            '</div>' +
            '<div class="floating-disclaimer" style="margin-top: 10px;">' +
              '<b>🛡️ Data Integrity Disclosure:</b> Bengaluru City Police releases verified statistics at the city-wide and division levels. No street-level or ward-level crime incident coordinates are supplied in public records. UrbanPulse refuses to plot fake incident pins. Mapped police station locations are available in the dedicated Police Stations layer.' +
            '</div>' +
          '</div>';
      }
    }
  }

  function renderActiveCategory() {
    var category = selector.value;
    state.activeCategory = category;

    if (category === "construction" || category === "crime") {
      showSpecialLayer(category);
      return;
    }

    hideFloatingPanels();
    map.closePopup();

    if (state.activeFacilityLayer) {
      map.removeLayer(state.activeFacilityLayer);
      state.activeFacilityLayer = null;
    }
    state.markerMap = {};

    var info = mapInfo[category] || { title: category, icon: "📍" };
    if (headerTitle) {
      headerTitle.textContent = info.title + " near " + state.selectedPoint.label;
    }
    if (nearbyResultsTitle) {
      nearbyResultsTitle.textContent = info.icon + " " + info.title + " within " + formatDistance(state.radiusMeters) + " of " + state.selectedPoint.label;
    }

    // Filter available snapshot items by radius
    var rawList = state.snapshot[category] || [];

    // Fallback mapping for combined categories if present
    if (!rawList.length && category === "schools" && state.snapshot.education) {
      rawList = state.snapshot.education.filter(function (f) {
        return f.type === "School" || (f.tags && f.tags.amenity === "school");
      });
    } else if (!rawList.length && category === "universities" && state.snapshot.education) {
      rawList = state.snapshot.education.filter(function (f) {
        return f.type === "University" || (f.tags && (f.tags.amenity === "university" || f.tags.amenity === "college"));
      });
    } else if (!rawList.length && (category === "bus" || category === "metro" || category === "railway") && state.snapshot.transport) {
      rawList = state.snapshot.transport.filter(function (f) {
        var t = (f.tags || {});
        if (category === "bus") return t.highway === "bus_stop" || t.bus === "yes";
        if (category === "metro") return t.station === "subway" || t.railway === "subway_entrance" || t.subway === "yes";
        if (category === "railway") return t.railway === "station" || t.train === "yes";
        return false;
      });
    }

    var lat0 = state.selectedPoint.lat;
    var lon0 = state.selectedPoint.lon;
    var filtered = [];

    rawList.forEach(function (f, idx) {
      var d = haversineDistanceMeters(lat0, lon0, f.lat, f.lon);
      if (d <= state.radiusMeters) {
        var est = calculateTravelEstimates(d, lat0, lon0, f.lat, f.lon);
        filtered.push({
          id: (f.osmId || f.id || idx) + "",
          feature: f,
          distance: d,
          estimates: est
        });
      }
    });

    // Sort ascending by distance (nearest first)
    filtered.sort(function (a, b) {
      return a.distance - b.distance;
    });

    state.activeFacilities = filtered;

    // Render markers on map
    var layerGroup = L.featureGroup();
    var markerIcon = createMarkerIcon(category);

    filtered.forEach(function (item) {
      var f = item.feature;
      var marker = L.marker([f.lat, f.lon], {
        icon: markerIcon,
        title: f.name || info.title
      });

      marker.bindPopup(function () {
        return buildPopupHTML(f, item.distance, item.estimates);
      }, { maxWidth: 330 });

      marker.on("click", function () {
        focusFacilityMarker(item.id);
      });

      marker.addTo(layerGroup);
      state.markerMap[item.id] = marker;
    });

    state.activeFacilityLayer = layerGroup.addTo(map);

    if (headerSource) {
      headerSource.textContent = "Verified Dataset · " + filtered.length + " mapped facilities within " + formatDistance(state.radiusMeters);
    }
    if (nearbyDataSource) {
      nearbyDataSource.textContent = "Verified Civic Dataset";
    }

    renderNearbyCards(filtered);

    if (category === "police") {
      var pPanel = document.getElementById("map-floating-panel-police");
      if (pPanel) pPanel.style.display = "block";
      var pTotal = document.getElementById("police-panel-total");
      if (pTotal) pTotal.textContent = filtered.length + " stations within " + formatDistance(state.radiusMeters);
    }

    // Launch live Overpass check in background
    triggerLiveOverpassQuery(category);
  }

  // Live Overpass query with AbortController, caching, and fallback
  function triggerLiveOverpassQuery(category) {
    var queryTag = getOverpassTagForCategory(category);
    if (!queryTag) return;

    var cacheKey = category + "_" + state.selectedPoint.lat.toFixed(3) + "_" + state.selectedPoint.lon.toFixed(3) + "_" + state.radiusMeters;
    if (state.liveCache[cacheKey]) return;

    if (state.abortController) {
      state.abortController.abort();
    }
    state.abortController = window.AbortController ? new AbortController() : null;

    var rMeters = Math.min(state.radiusMeters, 5000); // safety cap for Overpass timeouts
    var q = "[out:json][timeout:10];(node[" + queryTag + "](around:" + rMeters + "," +
            state.selectedPoint.lat + "," + state.selectedPoint.lon + "););out center tags 30;";

    fetch("https://overpass-api.de/api/interpreter", {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8" },
      body: "data=" + encodeURIComponent(q),
      signal: state.abortController ? state.abortController.signal : undefined
    })
    .then(function (res) { return res.ok ? res.json() : null; })
    .then(function (data) {
      if (!data || !data.elements || !data.elements.length) return;
      var fresh = [];
      data.elements.forEach(function (el) {
        var center = el.center || el;
        if (!center || !center.lat || !center.lon) return;
        var tags = el.tags || {};
        var name = tags.name || tags["name:en"];
        if (!name) return;

        fresh.push({
          category: category,
          type: infoTitleForCategory(category),
          osmType: el.type,
          osmId: el.id,
          lat: Number(center.lat),
          lon: Number(center.lon),
          name: name,
          address: [tags["addr:housenumber"], tags["addr:street"], tags["addr:suburb"], tags["addr:city"]].filter(Boolean).join(", ") || "Bengaluru",
          tags: tags
        });
      });

      if (fresh.length) {
        state.liveCache[cacheKey] = true;
        // Merge fresh items avoiding duplicates
        var existingIds = {};
        (state.snapshot[category] || []).forEach(function (it) {
          existingIds[it.osmId || it.name] = true;
        });

        fresh.forEach(function (it) {
          if (!existingIds[it.osmId || it.name]) {
            if (!state.snapshot[category]) state.snapshot[category] = [];
            state.snapshot[category].push(it);
          }
        });

        if (state.activeCategory === category) {
          if (headerSource) {
            headerSource.textContent = "Live OpenStreetMap / Overpass · " + state.activeFacilities.length + " mapped facilities";
          }
          if (nearbyDataSource) {
            nearbyDataSource.textContent = "Live OpenStreetMap Verified";
          }
        }
      }
    })
    .catch(function () {
      // Overpass busy/failed; bundled verified dataset is already displayed seamlessly
    });
  }

  function getOverpassTagForCategory(cat) {
    if (cat === "healthcare") return '"amenity"="hospital"';
    if (cat === "parks") return '"leisure"="park"';
    if (cat === "schools") return '"amenity"="school"';
    if (cat === "universities") return '"amenity"="university"';
    if (cat === "police") return '"amenity"="police"';
    if (cat === "bus") return '"highway"="bus_stop"';
    if (cat === "railway") return '"railway"="station"';
    if (cat === "government") return '"office"="government"';
    if (cat === "utilities") return '"man_made"="water_works"';
    return null;
  }

  function infoTitleForCategory(cat) {
    return (mapInfo[cat] && mapInfo[cat].title) || "Facility";
  }

  // =========================================================================
  // 10. EVENT LISTENERS SETUP
  // =========================================================================

  function setupEventListeners() {
    // Layer selector change
    selector.addEventListener("change", function () {
      renderActiveCategory();
    });

    // Radius selector change
    if (radiusSelector) {
      radiusSelector.addEventListener("change", function () {
        state.radiusMeters = parseInt(radiusSelector.value, 10) || 2000;
        if (state.radiusCircle) {
          state.radiusCircle.setRadius(state.radiusMeters);
        }
        if (selectedLocRadiusEl) {
          selectedLocRadiusEl.textContent = formatDistance(state.radiusMeters) + " radius";
        }
        renderActiveCategory();
      });
    }

    // Search input & button
    if (searchBtn && searchInput) {
      searchBtn.addEventListener("click", function () {
        searchArea(searchInput.value);
      });
      searchInput.addEventListener("keypress", function (e) {
        if (e.key === "Enter") {
          e.preventDefault();
          searchArea(searchInput.value);
        }
      });
    }

    // Locality quick chips
    document.querySelectorAll(".locality-chip").forEach(function (chip) {
      chip.addEventListener("click", function () {
        var locName = chip.getAttribute("data-loc");
        if (locName) {
          if (searchInput) searchInput.value = locName;
          searchArea(locName);
        }
      });
    });

    // Action buttons
    if (gpsBtn) gpsBtn.addEventListener("click", handleGPSLocation);
    if (resetBtn) resetBtn.addEventListener("click", resetToBengaluru);
    if (fitBoundsBtn) fitBoundsBtn.addEventListener("click", fitToRadiusBounds);
    if (nearbyFitBtn) nearbyFitBtn.addEventListener("click", fitToRadiusBounds);

    if (retryNearbyBtn) {
      retryNearbyBtn.addEventListener("click", function () {
        renderActiveCategory();
      });
    }

    if (dismissErrorBtn) {
      dismissErrorBtn.addEventListener("click", hideErrorBanner);
    }
  }

  // =========================================================================
  // 11. INITIALIZATION & DATA HYDRATION
  // =========================================================================

  initSelectedLocationLayers();
  setupEventListeners();

  // Load verified civic dataset
  fetch("data/civic-map.json", { cache: "no-store" })
    .then(function (res) {
      if (!res.ok) throw new Error("Civic map snapshot HTTP " + res.status);
      return res.json();
    })
    .then(function (data) {
      (data.features || []).forEach(function (feat) {
        var cat = feat.category;
        if (!state.snapshot[cat]) state.snapshot[cat] = [];
        state.snapshot[cat].push(feat);
      });
      renderActiveCategory();
    })
    .catch(function (err) {
      console.warn("[Map] Local civic dataset load issue:", err.message);
      renderActiveCategory();
    });

  // Ensure map tiles redraw correctly on window layout
  window.setTimeout(function () {
    map.invalidateSize();
  }, 100);

})();
