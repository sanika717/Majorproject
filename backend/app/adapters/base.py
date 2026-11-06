"""
UrbanPulse Data Adapter Interface and Data Classes.

Following the Adapter Design Pattern, BaseDataAdapter provides a standardized contract
for ingesting external heterogeneous datasets (BBMP work orders, crime statistics,
CPCB air quality, KSPCB water metrics, BESCOM electricity, and police geospatial data)
into the normalized UrbanPulse domain model.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session


class DataSourceStatus(str, Enum):
    ACTIVE = "active"
    DEGRADED = "degraded"
    OFFLINE = "offline"
    MAINTENANCE = "maintenance"


class DataQualityLevel(str, Enum):
    ACTUAL = "actual"          # Direct verified government sensor or official record
    ESTIMATED = "estimated"    # Calculated from empirical proxy or interpolated
    UNAVAILABLE = "unavailable"# Sensor offline or data missing


@dataclass
class ValidationResult:
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)
    data_quality: DataQualityLevel = DataQualityLevel.ACTUAL


@dataclass
class AdapterResult:
    source_name: str
    status: str  # "success", "partial", "failed"
    records_processed: int = 0
    records_failed: int = 0
    validation: Optional[ValidationResult] = None
    data_quality: DataQualityLevel = DataQualityLevel.ACTUAL
    provenance_hash: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    details: Dict[str, Any] = field(default_factory=dict)


class BaseDataAdapter(ABC):
    """
    Common data adapter interface for external datasets and data sources.
    Every adapter encapsulates:
      1. Data retrieval (fetch)
      2. Format normalization (normalize)
      3. Validation (validate)
      4. Missing-value handling (handle_missing)
      5. Ingestion / Persistence (ingest)
    """

    def __init__(self, source_name: str):
        self.source_name = source_name

    @abstractmethod
    def fetch(self, source_input: Any = None) -> Any:
        """Retrieve raw data from external API, file path, or payload."""
        pass

    @abstractmethod
    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Normalize external formats into unified internal dictionaries."""
        pass

    @abstractmethod
    def validate(self, normalized_data: List[Dict[str, Any]]) -> ValidationResult:
        """Validate format, schema, bounds, and mandatory fields."""
        pass

    @abstractmethod
    def handle_missing(self, normalized_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Handle missing, null, or out-of-range values deterministically without hallucination."""
        pass

    @abstractmethod
    def ingest(self, db: Session, raw_or_cleaned_data: Any) -> AdapterResult:
        """Execute the full pipeline: fetch -> normalize -> validate -> handle_missing -> persist."""
        pass
