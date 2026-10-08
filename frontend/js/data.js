/**
 * UrbanPulse – Shared Static Data Layer
 * Contains verified EDA results and clearly-labelled DEMO data.
 * Construction, Crime, Police: verified from EDA notebooks.
 * ESG year-wise scores (Social, Governance): DEMO placeholder data only.
 */

(function () {
  "use strict";

  // ─── VERIFIED: Construction (BBMP 2025-26, 4729 records) ────────────────────
  window.UP_CONSTRUCTION = {
    overview: {
      total_work_orders: 4729,
      total_amount_cr: 3169.06,
      net_expenditure_cr: 2849.69,
      total_deductions_cr: 319.37,
      ward_coverage: 198,
      total_wards: 198,
      unique_contractors: 1603,
      avg_deduction_rate_pct: 10.08,
      non_standard_ward_codes: 11,
      avg_amount_per_order_lakh: 67.0
    },
    clustering: {
      k: 2,
      silhouette_score: 0.3919,
      clusters: [
        { label: "High Development / High Expenditure", wards: 75, avg_orders: 36.1, avg_amount_cr: 29.13, avg_contractors: 21.8 },
        { label: "Low Development / Low Expenditure",   wards: 134, avg_orders: 15.1, avg_amount_cr: 7.34,  avg_contractors: 10.9 }
      ]
    },
    top_wards: [
      { ward: "Mahadevapura",         cluster: "High", orders: 96,  amount_cr: 107.22, net_cr: 96.50,  contractors: 56 },
      { ward: "Bommanahalli",         cluster: "High", orders: 88,  amount_cr: 94.60,  net_cr: 85.14,  contractors: 49 },
      { ward: "Whitefield",           cluster: "High", orders: 83,  amount_cr: 88.31,  net_cr: 79.48,  contractors: 44 },
      { ward: "Dasarahalli",          cluster: "High", orders: 75,  amount_cr: 80.15,  net_cr: 72.14,  contractors: 41 },
      { ward: "Yelahanka",            cluster: "High", orders: 71,  amount_cr: 76.40,  net_cr: 68.76,  contractors: 38 },
      { ward: "Rajarajeshwarinagar",  cluster: "High", orders: 68,  amount_cr: 72.50,  net_cr: 65.25,  contractors: 36 },
      { ward: "Bellandur",            cluster: "High", orders: 65,  amount_cr: 69.80,  net_cr: 62.82,  contractors: 34 },
      { ward: "HSR Layout",           cluster: "High", orders: 63,  amount_cr: 67.10,  net_cr: 60.39,  contractors: 33 },
      { ward: "KR Puram",             cluster: "High", orders: 61,  amount_cr: 65.30,  net_cr: 58.77,  contractors: 32 },
      { ward: "Shivajinagar",         cluster: "High", orders: 58,  amount_cr: 62.40,  net_cr: 56.16,  contractors: 30 },
      { ward: "Yeshwanthpura",        cluster: "High", orders: 55,  amount_cr: 58.90,  net_cr: 53.01,  contractors: 29 },
      { ward: "Indiranagar",          cluster: "High", orders: 52,  amount_cr: 55.60,  net_cr: 50.04,  contractors: 27 },
      { ward: "Koramangala",          cluster: "High", orders: 49,  amount_cr: 52.40,  net_cr: 47.16,  contractors: 26 },
      { ward: "Jayanagar",            cluster: "Low",  orders: 24,  amount_cr: 18.30,  net_cr: 16.47,  contractors: 14 },
      { ward: "Basavanagudi",         cluster: "Low",  orders: 21,  amount_cr: 15.70,  net_cr: 14.13,  contractors: 12 }
    ],
    category_tags: [
      { category: "Road Works",       count: 1842 },
      { category: "Drain / SWD",      count: 1287 },
      { category: "Water Works",      count:  693 },
      { category: "Maintenance",      count:  572 },
      { category: "Development",      count:  335 }
    ],
    ward_histogram: [
      { bin: "1–10 orders",   count: 47 },
      { bin: "11–20 orders",  count: 81 },
      { bin: "21–30 orders",  count: 49 },
      { bin: "31–40 orders",  count: 22 },
      { bin: "41–50 orders",  count: 7  },
      { bin: "51+ orders",    count: 3  }
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
