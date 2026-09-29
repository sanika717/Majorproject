from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class CrimeHistoricalOverview(BaseModel):
    period_label: str
    total_crimes: int
    fatal_crimes: int
    non_fatal_crimes: int
    fatal_percentage: float
    highest_risk_year: int
    highest_risk_score: float
    highest_risk_level: str
    highest_risk_volume_score: float
    highest_risk_severity_score: float

class CrimeRiskFormula(BaseModel):
    description: str
    volume_weight: float
    severity_weight: float
    thresholds: Dict[str, int]

class CrimeItemDetail(BaseModel):
    crime: Optional[str] = None
    division: Optional[str] = None
    cause: Optional[str] = None
    reported: Optional[int] = None
    detected: Optional[int] = None
    detection_pct: Optional[float] = None
    male: Optional[int] = None
    female: Optional[int] = None
    total: Optional[int] = None

class CrimeCategoryYearDetail(BaseModel):
    items: List[Dict[str, Any]]
    total_reported: Optional[int] = None
    total_detected: Optional[int] = None
    overall_detection_pct: Optional[float] = None
    total_suicides: Optional[int] = None
    total_accidental_deaths: Optional[int] = None
    total_male: Optional[int] = None
    total_female: Optional[int] = None

class CrimeCategoryDetail(BaseModel):
    title: str
    unit: str
    years: Dict[str, CrimeCategoryYearDetail]

class CrimeDataResponse(BaseModel):
    metadata: Dict[str, Any]
    historical: CrimeHistoricalOverview
    risk_formula: Dict[str, Any]
    categories: Dict[str, Any]

class CrimeAnalyticsQueryResponse(BaseModel):
    category: str
    year: Optional[str] = None
    title: str
    source: str
    methodology: str
    kpis: Dict[str, Any]
    items: List[Dict[str, Any]]
    chart_data: Dict[str, Any]
