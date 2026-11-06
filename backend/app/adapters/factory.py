"""
Adapter Factory Pattern for UrbanPulse Data Sources.
Enables dynamic discovery and instantiation of data adapters without coupling callers
to specific external format implementations.
"""

from typing import Dict, Type
from backend.app.adapters.base import BaseDataAdapter
from backend.app.adapters.bbmp_adapter import BbmpWorkOrderAdapter
from backend.app.adapters.crime_adapter import CrimeDataAdapter
from backend.app.adapters.aqi_adapter import AqiDataAdapter
from backend.app.adapters.water_adapter import WaterQualityAdapter
from backend.app.adapters.electricity_adapter import ElectricityDataAdapter
from backend.app.adapters.geospatial_adapter import GeospatialDataAdapter


class AdapterFactory:
    """Factory to retrieve appropriate data adapter based on source type."""

    _registry: Dict[str, Type[BaseDataAdapter]] = {
        "bbmp": BbmpWorkOrderAdapter,
        "bbmp_work_orders": BbmpWorkOrderAdapter,
        "construction": BbmpWorkOrderAdapter,
        "crime": CrimeDataAdapter,
        "crime_statistics": CrimeDataAdapter,
        "aqi": AqiDataAdapter,
        "air_quality": AqiDataAdapter,
        "environment": AqiDataAdapter,
        "water": WaterQualityAdapter,
        "water_quality": WaterQualityAdapter,
        "electricity": ElectricityDataAdapter,
        "energy": ElectricityDataAdapter,
        "bescom": ElectricityDataAdapter,
        "geospatial": GeospatialDataAdapter,
        "police_locations": GeospatialDataAdapter,
    }

    @classmethod
    def get_adapter(cls, source_type: str) -> BaseDataAdapter:
        norm_type = source_type.strip().lower()
        adapter_cls = cls._registry.get(norm_type)
        if not adapter_cls:
            raise ValueError(
                f"Unsupported adapter source type: '{source_type}'. "
                f"Supported types: {list(cls._registry.keys())}"
            )
        return adapter_cls()

    @classmethod
    def register_adapter(cls, source_type: str, adapter_cls: Type[BaseDataAdapter]) -> None:
        """Allow plugins or future services to register new adapters at runtime."""
        cls._registry[source_type.strip().lower()] = adapter_cls
