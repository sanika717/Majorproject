from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class ConstructionOverview(BaseModel):
    total_work_orders: int
    total_amount: int
    total_net_expenditure: int
    total_deduction: int
    avg_deduction_rate_pct: float
    unique_contractors: int
    distinct_ward_values: int
    official_numbered_wards_present: int
    official_wards_total: int
    non_standard_ward_codes_present: int

class ClusterStat(BaseModel):
    cluster: int
    cluster_name: str
    ward_count: int
    avg_work_orders: float
    avg_total_amount: float
    avg_net_expenditure: float
    avg_deduction: float
    avg_contractors: float

class ClusteringOverview(BaseModel):
    method: str
    features_used: List[str]
    silhouette_by_k: Dict[str, float]
    chosen_k: int
    chosen_k_rationale: str
    clusters: List[ClusterStat]

class WardSummaryItem(BaseModel):
    ward: str
    total_work_orders: int
    total_amount: int
    avg_project_amount: float
    total_net_expenditure: int
    avg_net_amount: float
    total_deduction: int
    avg_deduction: float
    unique_contractors: int
    drain_projects: int
    road_projects: int
    maintenance_projects: int
    development_projects: int
    water_projects: int
    cluster: int
    cluster_name: str

class TopWardItem(BaseModel):
    ward: str
    cluster_name: str
    total_work_orders: int
    total_amount: int
    total_net_expenditure: Optional[int] = None
    unique_contractors: int

class ConstructionDataResponse(BaseModel):
    metadata: Dict[str, Any]
    overview: ConstructionOverview
    clustering: ClusteringOverview
    top_wards_by_investment: List[TopWardItem]
    top_wards_by_work_orders: List[TopWardItem]
    category_tags: Dict[str, int]
    ward_level_data: Optional[List[WardSummaryItem]] = None
