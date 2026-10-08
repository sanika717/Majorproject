# ESG data (frontend/data/esg)

These JSON files contain source-attributed ESG records. Reporting periods and geographic scope are preserved from each source. The backend seeds them into the database on startup (`backend/app/services/esg_service.py`, tables `esg_*`) and the frontend falls back to them if the API is unavailable.

| File | Content | Source |
|---|---|---|
| sources.json | Source URL, publisher, period for every dataset | - |
| air_quality_stations.json | KSPCB manual station observations and published city averages, 2016-17 | Guttikunda et al. 2019, using KSPCB monitoring data; standards linked to CPCB NAAQS |
| carbon_emissions.json | BBMP-area GHG inventory total and sector shares, base year 2019; no sector tonnes inferred | BBMP BCAP |
| water_quality_lakes_2020_21.json | Monthly class + WQI status, Apr 2020-Mar 2021 | KSPCB MINARS CSV, Bangalore Urban/Rural districts |
| electricity_consumption.json | Empty: no genuine area-wise data found | BESCOM / data.gov.in (reference only) |
| official_metrics.csv | Optional manual rows (see header) that override/extend scoring metrics | - |

The ESG page calculates pollutant headroom against the registered CPCB standards and uses the reported satisfactory water station-month percentage directly. It equally weights available, scored environmental indicators for the displayed environmental score. Overall score remains unavailable until all categories have comparable source-backed scores. Historic years are never relabeled as the current year.

To add new source data, register the source and its geography in `sources.json`, then ingest verified records through the backend update jobs or the documented JSON import. Never estimate missing observations or derive sector tonnes from percentages.

## Auto-update (Phase 1)
`backend/app/services/esg_update/` refreshes the database in the background (see its `scheduler.py` header for env vars).
Air = CPCB feed on data.gov.in (needs `DATA_GOV_IN_API_KEY`), electricity = BESCOM CSV via OpenCity, carbon/water = reload
when the verified JSON here changes. Check `GET /api/v1/esg/update-status`. Never add estimated values.
