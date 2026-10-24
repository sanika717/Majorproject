"""
Pydantic schemas for the UrbanPulse Intelligence Assistant and UrbanScore.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=1000, description="User civic query")
    locality: Optional[str] = Field(None, max_length=100, description="Optional Bengaluru locality name")
    enable_cache: bool = Field(True, description="Whether to check and update Redis semantic cache")


class SourceReference(BaseModel):
    name: str
    record_count: Optional[str] = None
    period: Optional[str] = None
    verified: bool = True
    authority: Optional[str] = None


class DecisionAnalysisSchema(BaseModel):
    verdict: Optional[str] = None
    reasons_to_consider: List[str] = Field(default_factory=list)
    reasons_for_caution: List[str] = Field(default_factory=list)
    risks: Dict[str, List[str]] = Field(default_factory=dict)
    recommendations: List[str] = Field(default_factory=list)
    missing_data_warnings: List[str] = Field(default_factory=list)


class AskResponse(BaseModel):
    question: str
    locality: Optional[str] = None
    answer: str
    urban_score: Optional[Dict[str, Any]] = None
    analysis: Optional[Dict[str, Any]] = None
    sources: List[Any] = Field(default_factory=list)
    answer_mode: str = "UrbanPulse Data + AI Analysis"  # Level label
    cached: bool = False
    cache_status: str = "miss"
    similarity: Optional[float] = None
    cache_similarity: Optional[float] = None
    model: str = "qwen3:8b"
    latency_ms: float = 0.0



class UrbanScoreResponse(BaseModel):
    locality: str
    ward_no: Optional[str] = None
    ward_name: Optional[str] = None
    score: float
    grade: str
    components: Dict[str, Any]
    weights_applied: Dict[str, float]
    data_coverage_pct: float
    confidence: str
    missing_metrics: List[str]
    limitations: List[str]
    last_updated: str


class CompareResponse(BaseModel):
    areas: List[str]
    scores: List[Dict[str, Any]]
    comparison_summary: str
    winner_overall: Optional[str] = None
    metrics_table: List[Dict[str, Any]]
