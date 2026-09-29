from typing import Optional, Dict, Any
from pydantic import BaseModel

class DashboardHeadlineKPIs(BaseModel):
    total_work_orders: int
    total_construction_investment: int
    total_construction_investment_formatted: str
    total_recorded_crimes: int
    crimes_period_label: str
    mapped_police_locations: int
    highest_risk_score: float
    highest_risk_level: str
    highest_risk_year: int
    wards_covered_official: int
    wards_total_official: int
    unique_contractors: int
    fatal_crimes: int
    non_fatal_crimes: int
    fatal_percentage: float

class DashboardOverviewResponse(BaseModel):
    kpis: DashboardHeadlineKPIs
    active_layers: list[str]
