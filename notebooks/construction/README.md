# Construction EDA — Notebook Provenance

- `urbanpulse__edaipynb.py` — the original Colab-exported notebook as provided. Its construction-specific
  cells (cleaning, ward aggregation, work-category tagging, K-Means++ clustering) are the source of truth
  for the logic used in the dashboard. Its unrelated cells that download and cluster a separate
  "Bangalore City Traffic" dataset via `kagglehub` are **out of scope** for this integration and were not
  executed (they also reference an undefined `traffic_ml` variable partway through, so that section would
  not run as-is).
- `construction_eda_runner.py` — a clean re-implementation of exactly the notebook's construction-only
  cells (same column names, same feature engineering, same `KMeans(n_clusters=2, random_state=42, n_init=10)`
  call as the notebook's final labeled clustering), run directly against
  `data/construction/bbmp-2025-26-198-wards-work-orders.csv`. This is what produced
  `data/construction/construction_data.json` and `frontend/js/construction-data.js`. Re-running it against
  the same CSV reproduces identical output (silhouette scores, cluster assignments, KPI totals).

Two K-Means passes exist in the original notebook: an earlier exploratory one (log-transformed financial
features only, hardcoded `BEST_K = 4`) and a later, final one (13 features including work-category tags,
`final_kmeans = KMeans(n_clusters=2, ...)`, with human-readable cluster names). The dashboard uses the
**final** pipeline — it's the one the notebook actually names and narrates ("High Development / High
Expenditure" vs "Low Development / Low Expenditure"), and K=2 also has the best silhouette score (0.392)
of any K from 2–8 tested on those features, so it isn't an arbitrary pick.
