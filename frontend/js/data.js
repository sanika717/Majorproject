/**
 * UrbanPulse – Shared Static Data Layer
 * Contains verified EDA results and clearly-labelled DEMO data.
 * Construction, Crime, Police: verified from EDA notebooks.
 * ESG year-wise scores (Social, Governance): DEMO placeholder data only.
 */

(function () {
  "use strict";

  // ─── VERIFIED: Construction (BBMP 2025-26, 4729 records) ────────────────────
  // ─── VERIFIED: Construction (BBMP 2025-26, 4,729 records, 209 ward codes) ──
  window.UP_CONSTRUCTION = {
    overview: {
      total_work_orders: 4729,
      total_amount_cr: 3169.06,
      net_expenditure_cr: 2857.58,
      total_deductions_cr: 311.48,
      ward_coverage: 198,
      total_wards: 198,
      distinct_ward_values: 209,
      unique_contractors: 1603,
      avg_deduction_rate_pct: 10.08,
      non_standard_ward_codes: 11,
      avg_amount_per_order_lakh: 67.01
    },
    clustering: {
      k: 2,
      silhouette_score: 0.3919,
      clusters: [
        { label: "High Development / High Expenditure", wards: 75, avg_orders: 36.12, avg_amount_cr: 29.13, avg_contractors: 21.81 },
        { label: "Low Development / Low Expenditure",   wards: 134, avg_orders: 15.07, avg_amount_cr: 7.34,  avg_contractors: 10.9 }
      ]
    },
    top_wards: [
      { ward: "Ward 175", cluster: "High Development", orders: 43, amount_cr: 56.42, net_cr: 52.75, contractors: 21 },
      { ward: "Ward 150", cluster: "High Development", orders: 54, amount_cr: 55.51, net_cr: 50.46, contractors: 28 },
      { ward: "Ward 54",  cluster: "High Development", orders: 45, amount_cr: 55.37, net_cr: 50.88, contractors: 27 },
      { ward: "Ward 4",   cluster: "High Development", orders: 62, amount_cr: 51.95, net_cr: 48.63, contractors: 40 },
      { ward: "Ward 184", cluster: "High Development", orders: 46, amount_cr: 49.56, net_cr: 45.52, contractors: 32 },
      { ward: "Ward 25",  cluster: "High Development", orders: 31, amount_cr: 49.55, net_cr: 45.33, contractors: 17 },
      { ward: "Ward 159", cluster: "High Development", orders: 39, amount_cr: 48.95, net_cr: 44.81, contractors: 20 },
      { ward: "Ward 3",   cluster: "High Development", orders: 73, amount_cr: 48.86, net_cr: 45.41, contractors: 47 },
      { ward: "Ward 194", cluster: "High Development", orders: 38, amount_cr: 48.26, net_cr: 45.18, contractors: 28 },
      { ward: "Ward 153", cluster: "High Development", orders: 56, amount_cr: 45.55, net_cr: 43.12, contractors: 26 },
      { ward: "Ward 1",   cluster: "High Development", orders: 50, amount_cr: 45.23, net_cr: 42.22, contractors: 32 },
      { ward: "Ward 198", cluster: "High Development", orders: 36, amount_cr: 44.89, net_cr: 37.91, contractors: 17 },
      { ward: "Ward 58",  cluster: "High Development", orders: 25, amount_cr: 42.49, net_cr: 36.37, contractors: 17 },
      { ward: "Ward 65",  cluster: "High Development", orders: 34, amount_cr: 42.05, net_cr: 38.49, contractors: 20 },
      { ward: "Ward 35",  cluster: "High Development", orders: 30, amount_cr: 40.50, net_cr: 37.58, contractors: 21 }
    ],
    top_wards_by_work_orders: [
      { ward: "Ward 3",   cluster: "High Development", orders: 73, amount_cr: 48.86, net_cr: 45.41, contractors: 47 },
      { ward: "Ward 4",   cluster: "High Development", orders: 62, amount_cr: 51.95, net_cr: 48.63, contractors: 40 },
      { ward: "Ward 26",  cluster: "High Development", orders: 61, amount_cr: 33.13, net_cr: 30.34, contractors: 25 },
      { ward: "Ward 44",  cluster: "High Development", orders: 57, amount_cr: 33.83, net_cr: 31.39, contractors: 24 },
      { ward: "Ward 153", cluster: "High Development", orders: 56, amount_cr: 45.55, net_cr: 43.12, contractors: 26 },
      { ward: "Ward 150", cluster: "High Development", orders: 54, amount_cr: 55.51, net_cr: 50.46, contractors: 28 },
      { ward: "Ward 1",   cluster: "High Development", orders: 50, amount_cr: 45.23, net_cr: 42.22, contractors: 32 },
      { ward: "Ward 184", cluster: "High Development", orders: 46, amount_cr: 49.56, net_cr: 45.52, contractors: 32 },
      { ward: "Ward 54",  cluster: "High Development", orders: 45, amount_cr: 55.37, net_cr: 50.88, contractors: 27 },
      { ward: "Ward 175", cluster: "High Development", orders: 43, amount_cr: 56.42, net_cr: 52.75, contractors: 21 }
    ],
    category_tags: [
      { category: "Road Works",       count: 2327 },
      { category: "Development",      count: 2063 },
      { category: "Drain / SWD",      count: 1514 },
      { category: "Maintenance",      count:  795 },
      { category: "Water Works",      count:  397 }
    ],
    ward_histogram: [
      { bin: "1–10 orders",   count: 30 },
      { bin: "11–20 orders",  count: 78 },
      { bin: "21–30 orders",  count: 54 },
      { bin: "31–40 orders",  count: 21 },
      { bin: "41–50 orders",  count: 17 },
      { bin: "51+ orders",    count:  9 }
    ]
  };

  // ─── VERIFIED: Crime & Safety (Bengaluru City Police, D47 + Press Note) ─────
  window.UP_CRIME = {
    // 2014–2021 D47 aggregate
    overall: {
      period: "2014–2021",
      total: 35971,
      fatal: 5437,
      non_fatal: 30534,
      fatal_pct: 15.11
    },
    risk: {
      score: 71.7,
      level: "High Risk",
      peak_year: 2016,
      volume_score: 100.0,
      severity_score: 29.26
    },
    // Annual D47 totals 2014-2021
    d47_annual: [
      { year: 2014, total: 4820, fatal: 729  },
      { year: 2015, total: 4933, fatal: 742  },
      { year: 2016, total: 5612, fatal: 847  },
      { year: 2017, total: 5108, fatal: 770  },
      { year: 2018, total: 4687, fatal: 707  },
      { year: 2019, total: 4392, fatal: 662  },
      { year: 2020, total: 3702, fatal: 558  },
      { year: 2021, total: 2717, fatal: 422  }
    ],
    // Category-level breakdown
    categories: {
      all: [
        { crime_type: "Murder",                      reported: 372,  detected_fatal: 372,  rate_pct: 100.0 },
        { crime_type: "Attempt to Murder",            reported: 1101, detected_fatal: 1101, rate_pct: 100.0 },
        { crime_type: "Robbery",                      reported: 1247, detected_fatal: null, rate_pct: null  },
        { crime_type: "Dacoity",                      reported:  98,  detected_fatal: null, rate_pct: null  },
        { crime_type: "Burglary",                     reported: 6821, detected_fatal: null, rate_pct: null  },
        { crime_type: "Theft",                        reported: 13804,detected_fatal: null, rate_pct: null  },
        { crime_type: "Cheating",                     reported: 2814, detected_fatal: null, rate_pct: null  },
        { crime_type: "Causing Death by Negligence",  reported: 1477, detected_fatal: 1477, rate_pct: 100.0 },
        { crime_type: "Hurt",                         reported: 3246, detected_fatal: null, rate_pct: null  },
        { crime_type: "Kidnapping",                   reported:  991, detected_fatal: null, rate_pct: null  }
      ],
      women: {
        source: "Bengaluru City Police Annual Report / Press Note",
        by_year: [
          { year: 2021, cases: 2934 },
          { year: 2022, cases: 3167 },
          { year: 2023, cases: 3401 }
        ],
        subtypes_2023: [
          { type: "Domestic Violence", cases: 1218 },
          { type: "Outraging Modesty", cases:  542 },
          { type: "Sexual Harassment", cases:  319 },
          { type: "Molestation",       cases:  287 },
          { type: "Rape",              cases:  241 },
          { type: "Dowry Offences",    cases:  196 },
          { type: "Trafficking",       cases:   78 },
          { type: "Others",            cases:  520 }
        ]
      },
      children: {
        source: "Bengaluru City Police Annual Report / Press Note",
        by_year: [
          { year: 2021, cases:  623 },
          { year: 2022, cases:  698 },
          { year: 2023, cases:  741 }
        ],
        subtypes_2023: [
          { type: "POCSO",                 cases: 312 },
          { type: "Kidnapping",            cases: 198 },
          { type: "Child Labour",          cases:  87 },
          { type: "Missing Children",      cases: 144 }
        ]
      },
      cyber: {
        source: "Bengaluru City Police Annual Report / Press Note",
        by_year: [
          { year: 2021, cases:  8136 },
          { year: 2022, cases: 10871 },
          { year: 2023, cases: 13534 }
        ],
        by_division_2023: [
          { division: "South",      cases: 3812 },
          { division: "East",       cases: 2946 },
          { division: "North",      cases: 2641 },
          { division: "West",       cases: 1876 },
          { division: "CID / Misc", cases: 2259 }
        ]
      },
      suicides: {
        source: "Bengaluru City Police Annual Report / Press Note",
        by_year: [
          { year: 2021, deaths: 1872 },
          { year: 2022, deaths: 2014 },
          { year: 2023, deaths: 2103 }
        ]
      },
      accidental: {
        source: "Bengaluru City Police Annual Report / Press Note",
        by_year: [
          { year: 2021, deaths: 2641 },
          { year: 2022, deaths: 2793 },
          { year: 2023, deaths: 2887 }
        ]
      }
    }
  };

  // ─── VERIFIED: Police Locations (Karnataka State Police KML) ─────────────────
  window.UP_POLICE = {
    source: "Karnataka State Police GIS KML Files",
    total: 150,
    by_type: [
      { type: "Police Station",  count: 112, source_kml: "bengaluru_city_police_stations.kml" },
      { type: "Police Outpost",  count:  38, source_kml: "bengaluru_city_police_outposts.kml" }
    ]
  };

  // ─── DEMO: ESG Year-wise data (DEMO/PLACEHOLDER ONLY – replace with real data) ──
  // Labelled prominently. Real Environmental data comes from esg-env.js.
  window.UP_ESG_DEMO = {
    _notice: "DEMO DATA: Social, Governance, and composite scores are illustrative placeholders only. Environmental data is real (KSPCB/CPCB/BCAP). Replace this section with verified source data before production use.",
    years: [2021, 2022, 2023],
    environmental: {
      _source: "Real: KSPCB Air Quality 2016-17 / KSPCB MINARS 2020-21 (actual values from esg-env.js)",
      scores: { 2021: null, 2022: null, 2023: null } // driven by live esg-env.js data
    },
    social: {
      _source: "DEMO – No verified social index source connected yet",
      scores: { 2021: 54.2, 2022: 57.8, 2023: 61.3 },
      indicators: [
        { name: "Literacy Rate",             value: "88.5%",  note: "DEMO" },
        { name: "Access to Piped Water",     value: "74.3%",  note: "DEMO" },
        { name: "Hospital Beds / 1000",      value: "1.9",    note: "DEMO" },
        { name: "School Enrolment",          value: "93.2%",  note: "DEMO" }
      ]
    },
    governance: {
      _source: "DEMO – No verified governance index source connected yet",
      scores: { 2021: 46.1, 2022: 49.5, 2023: 52.7 },
      indicators: [
        { name: "Budget Utilisation",        value: "81.4%",  note: "DEMO" },
        { name: "Complaint Resolution Rate", value: "63.2%",  note: "DEMO" },
        { name: "Transparency Index",        value: "52 / 100", note: "DEMO" },
        { name: "Audit Observations Cleared", value: "78.1%", note: "DEMO" }
      ]
    },
    carbon: {
      _source: "Real: BCAP 2019 GHG Inventory (illustrative year-wise change below is DEMO)",
      scores: { 2021: null, 2022: null, 2023: null },
      emissions_mmt: { 2019: 23.74, 2021: 22.1, 2022: 23.0, 2023: 24.3 }
    }
  };

})();
