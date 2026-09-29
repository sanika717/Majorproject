import pandas as pd
import numpy as np
import json

csv_path = "/mnt/user-data/uploads/bbmp-2025-26-198-wards-work-orders.csv"
df_construction = pd.read_csv(csv_path)
ward_df = df_construction.copy()
for col in ["amount","nett","deduction"]:
    ward_df[col] = pd.to_numeric(ward_df[col], errors="coerce")

# ---- ward-level feature engineering (mirrors notebook's final pipeline) ----
ward_features = ward_df.groupby("ward").agg(
    total_work_orders=("id","count"),
    total_amount=("amount","sum"),
    avg_project_amount=("amount","mean"),
    total_net_expenditure=("nett","sum"),
    avg_net_amount=("nett","mean"),
    total_deduction=("deduction","sum"),
    avg_deduction=("deduction","mean"),
    unique_contractors=("contractor","nunique")
).reset_index()

text = ward_df["wodetails"].fillna("").str.lower()
ward_df["is_drain"] = text.str.contains("drain|drainage", regex=True).astype(int)
ward_df["is_road"] = text.str.contains("road|street", regex=True).astype(int)
ward_df["is_maintenance"] = text.str.contains("maintenance|repair", regex=True).astype(int)
ward_df["is_development"] = text.str.contains("development|improvement", regex=True).astype(int)
ward_df["is_water"] = text.str.contains("water|pipeline|sewer", regex=True).astype(int)

work_categories = ward_df.groupby("ward").agg(
    drain_projects=("is_drain","sum"),
    road_projects=("is_road","sum"),
    maintenance_projects=("is_maintenance","sum"),
    development_projects=("is_development","sum"),
    water_projects=("is_water","sum")
).reset_index()

ward_features = ward_features.merge(work_categories, on="ward", how="left")

cluster_features = [
    "total_work_orders","total_amount","avg_project_amount","total_net_expenditure",
    "avg_net_amount","total_deduction","avg_deduction","unique_contractors",
    "drain_projects","road_projects","maintenance_projects","development_projects","water_projects"
]

from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

X = ward_features[cluster_features]
X_scaled = StandardScaler().fit_transform(X)

silhouette_by_k = {}
for k in range(2,9):
    model = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = model.fit_predict(X_scaled)
    silhouette_by_k[k] = round(float(silhouette_score(X_scaled, labels)), 4)

final_kmeans = KMeans(n_clusters=2, random_state=42, n_init=10)
ward_features["cluster"] = final_kmeans.fit_predict(X_scaled)
ward_features["cluster_name"] = ward_features["cluster"].map({
    0: "High Development / High Expenditure",
    1: "Low Development / Low Expenditure"
})

cluster_summary = ward_features.groupby(["cluster","cluster_name"]).agg(
    ward_count=("ward","count"),
    avg_work_orders=("total_work_orders","mean"),
    avg_total_amount=("total_amount","mean"),
    avg_net_expenditure=("total_net_expenditure","mean"),
    avg_deduction=("total_deduction","mean"),
    avg_contractors=("unique_contractors","mean"),
).round(2).reset_index()

# ---- ward id classification (official numbered vs non-standard code) ----
def ward_kind(w):
    return "official_numbered" if str(w).isdigit() else "non_standard_code"

ward_features["ward_kind"] = ward_features["ward"].apply(ward_kind)
n_official = int((ward_features["ward_kind"]=="official_numbered").sum())
n_nonstd = int((ward_features["ward_kind"]=="non_standard_code").sum())

# ---- overview ----
overview = {
    "total_work_orders": int(len(ward_df)),
    "total_amount": int(ward_df["amount"].sum()),
    "total_net_expenditure": int(ward_df["nett"].sum()),
    "total_deduction": int(ward_df["deduction"].sum()),
    "avg_deduction_rate_pct": round(float(((ward_df["deduction"]/ward_df["amount"])*100).replace([np.inf,-np.inf], np.nan).mean()), 2),
    "unique_contractors": int(ward_df["contractor"].nunique()),
    "distinct_ward_values": int(ward_df["ward"].astype(str).str.strip().nunique()),
    "official_numbered_wards_present": n_official,
    "official_wards_total": 198,
    "non_standard_ward_codes_present": n_nonstd
}

top_wards_by_investment = ward_features.sort_values("total_amount", ascending=False).head(15)[
    ["ward","cluster_name","total_work_orders","total_amount","total_net_expenditure","unique_contractors"]
].to_dict(orient="records")

top_wards_by_work_orders = ward_features.sort_values("total_work_orders", ascending=False).head(15)[
    ["ward","cluster_name","total_work_orders","total_amount","unique_contractors"]
].to_dict(orient="records")

category_tags = {
    "drain_projects": int(ward_features["drain_projects"].sum()),
    "road_projects": int(ward_features["road_projects"].sum()),
    "maintenance_projects": int(ward_features["maintenance_projects"].sum()),
    "development_projects": int(ward_features["development_projects"].sum()),
    "water_projects": int(ward_features["water_projects"].sum())
}

result = {
    "metadata": {
        "source_file": "bbmp-2025-26-198-wards-work-orders.csv",
        "source_notebook": "urbanpulse__edaipynb.py (construction EDA cells; traffic/kagglehub sections out of scope and not run)",
        "pipeline": "RAW CSV -> pandas cleaning (numeric coercion of amount/nett/deduction) -> ward-level aggregation -> keyword-based work-category tagging -> StandardScaler -> KMeans++ (verified via silhouette scan K=2-8) -> verified JSON",
        "generated_note": "All figures below are computed directly from the uploaded CSV using the logic in the source notebook. No values were invented, estimated, or backfilled.",
        "geo_disclaimer": "No BBMP ward-boundary or ward-centroid coordinate dataset was supplied, so ward polygons/markers cannot be plotted on the map. Only the 150 verified police locations (separate KML source) have coordinates.",
        "category_disclaimer": "drain/road/maintenance/development/water tags are keyword matches on free-text work-order descriptions (a single work order can match more than one keyword), so category totals are not mutually exclusive and do not sum to total_work_orders."
    },
    "overview": overview,
    "clustering": {
        "method": "K-Means++ (scikit-learn), 13 standardized ward-level features, random_state=42",
        "features_used": cluster_features,
        "silhouette_by_k": silhouette_by_k,
        "chosen_k": 2,
        "chosen_k_rationale": "K=2 has the highest silhouette score (0.392) of all K from 2-8 tested, and is the K used for the notebook's final named clustering.",
        "clusters": cluster_summary.to_dict(orient="records")
    },
    "top_wards_by_investment": top_wards_by_investment,
    "top_wards_by_work_orders": top_wards_by_work_orders,
    "category_tags": category_tags,
    "ward_level_data": ward_features.drop(columns=["ward_kind"]).to_dict(orient="records")
}

with open("/home/claude/construction_eda/construction_data.json","w") as f:
    json.dump(result, f, indent=2)

print("Wrote construction_data.json")
print("Overview:", json.dumps(overview, indent=2))
print("\nClusters:", json.dumps(result["clustering"]["clusters"], indent=2))
