# Majorproject: UrbanPulse — Smart City Transparency Platform

**UrbanPulse** is an evidence-based Smart City Transparency and Civic Intelligence platform for Bengaluru, integrating real-time geospatial layers, verified municipal statistics, and reproducible EDA.

```
                    URBANPULSE
           Smart City Transparency Platform
                         |
                         ↓
              🗺️ SMART CITY MAP
                         |
          ┌──────────────┼──────────────┐
          ↓              ↓              ↓
    Construction      Crime         Healthcare
          ↓              ↓              ↓
       Parks          Police        Education
          ↓              ↓              ↓
     Transport       Utilities     Government
                         |
                         ↓
                 Analytics / EDA
                         |
                         ↓
                Insights / Trends
```

---

## 🏛️ Project Directory Structure

```
UrbanPulse/
├── frontend/
│   ├── index.html            # Redirects to dashboard.html
│   ├── dashboard.html        # USER › Dashboard (map-first: one Leaflet map + 4 headline KPIs)
│   ├── analytics.html        # USER › Analytics (Crime + Construction EDA, moved unchanged)
│   ├── complaints.html       # USER › Public Complaints (placeholder)
│   ├── assistant.html        # USER › Intelligence Assistant (placeholder)
│   ├── css/
│   │   └── style.css         # Modern Dark Glassmorphic Design System
│   └── js/
│       ├── data.js           # Verified Real Datasets (Bengaluru Police)
│       ├── locations.js      # 150 Verified Mapped Police Locations
│       ├── map.js            # Unified Smart City Map (Leaflet + OpenStreetMap tiles, no API key)
│       ├── dashboard.js      # Dashboard headline KPIs (read from verified datasets)
│       ├── crime.js          # Crime & Safety Analytics Engine & Charts
│       ├── construction-data.js  # Verified BBMP ward work-order EDA results
│       ├── construction.js   # Construction Analytics (KPIs, clusters, charts, table)
│       └── app.js            # Global App Controller & Event Bus
├── data/
│   ├── kml/                  # Bengaluru Police Geospatial KML Files
│   ├── crime/                # Cleaned Crime JSON Datasets
│   └── construction/         # BBMP work-order CSV + verified EDA JSON/CSV
├── notebooks/
│   ├── crime/                # Crime & Safety EDA Notebooks
│   │   └── UrbanPulse_Crime_EDA.ipynb
│   └── construction/         # Original notebook + reproducible runner script
├── index.html                # Root entrypoint → frontend/dashboard.html
└── README.md
```

---

## 🔒 Verification & Transparency Principles

1. **Zero Fabricated Statistics**: Every metric is strictly sourced from verified official records (Bengaluru City Police Annual Reports, D47 Crime Statistics, Open City portal).
2. **Strict Data Scope Distinction**: Station-level pins display official geographical coordinates from the 150 KML locations; crime statistics are clearly designated as **Bengaluru city-level / division-level totals** to maintain institutional credibility.
3. **EDA-First Incremental Growth**:
   - **EDA Completed** $\rightarrow$ Connected directly into the interactive dashboard and map layer.
   - **Construction (LIVE)** $\rightarrow$ 4,729 BBMP work orders, 209 ward codes, K-Means++ development clusters. No ward-boundary coordinates were supplied, so the map layer shows a live KPI panel rather than ward markers.
   - **Crime & Safety (LIVE)** $\rightarrow$ city/division-level 2021–2023 categories (Women, Children, Cyber, Suicides, Accidental Deaths) + D47 2014–2021 overview. The Police Stations layer shows the 150 KML locations with no station-level crime numbers.
   - **EDA In Progress / Coming Soon** $\rightarrow$ Preserves clean visual UI structure with clear placeholder status tags; no fake numbers or simulated records.

---

## 🚀 Getting Started

Run a lightweight local web server (recommended: OpenStreetMap's tile servers expect a Referer header, which `file://` pages do not send):

```bash
# From inside UrbanPulse directory:
python3 -m http.server 8080
```
Then visit: `http://localhost:8080/frontend/dashboard.html`
