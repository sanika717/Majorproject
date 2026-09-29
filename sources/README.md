# Sources

Raw materials behind the verified figures in `frontend/js/data.js` / `data/crime/crime_data.json`:

- `Bengaluru_Police_PressNote_2021-2023.pdf` — Bengaluru City Police Press Note. Primary source for the
  Women, Children, Cyber Crime, and Suicides/Accidental Deaths 2021–2023 tables shown in the Crime & Safety layer.
- `D47-Crimes (1)_1_0.csv` — D47 city-level Fatal/Non-Fatal crime series (2014–2021), source of the
  "historical" overview KPI card and the UrbanPulse Risk Score.
- `dc918a6a-...csv`, `57a5a08f-...csv`, `5fcc276e-...csv` — extracted tabular versions of the Women /
  Children / Suicides & Accidental Deaths tables from the press note, used to cross-check the numbers above.
- `urbanpulse2.py`, `urbanpulse__edaipynb.py` — Colab-exported EDA scripts. `urbanpulse__edaipynb.py`
  contains ward-level BBMP construction EDA code, but it reads from
  `bbmp-2025-26-198-wards-work-orders.csv`, which was never supplied, so that code has not been run and
  produced no verified output. This is why the Construction map layer still shows "EDA In Progress" —
  there are no real KPIs, ward figures, or K-Means clusters to display yet.
