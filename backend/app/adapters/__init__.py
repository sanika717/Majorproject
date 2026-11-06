"""
UrbanPulse Adapters Module.
Implements the Adapter Design Pattern for external dataset normalization, validation,
and deterministic ingestion.
"""

from backend.app.adapters.base import (
    BaseDataAdapter,
    ValidationResult,
    AdapterResult,
    DataQualityLevel,
    DataSourceStatus,
)
from backend.app.adapters.bbmp_adapter import BbmpWorkOrderAdapter
from backend.app.adapters.crime_adapter import CrimeDataAdapter
from backend.app.adapters.aqi_adapter import AqiDataAdapter
from backend.app.adapters.water_adapter import WaterQualityAdapter
from backend.app.adapters.electricity_adapter import ElectricityDataAdapter
from backend.app.adapters.geospatial_adapter import GeospatialDataAdapter
from backend.app.adapters.factory import AdapterFactory

__all__ = [
    "BaseDataAdapter",
    "ValidationResult",
    "AdapterResult",
    "DataQualityLevel",
    "DataSourceStatus",
    "BbmpWorkOrderAdapter",
    "CrimeDataAdapter",
    "AqiDataAdapter",
    "WaterQualityAdapter",
    "ElectricityDataAdapter",
    "GeospatialDataAdapter",
    "AdapterFactory",
]
