"""
Geospatial Data Adapter.
Handles external GeoJSON/KML spatial feeds, police station locations, ward boundaries,
and coordinate bounds validation for Bengaluru metropolitan region.
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from backend.app.adapters.base import (
    BaseDataAdapter,
    ValidationResult,
    AdapterResult,
    DataQualityLevel,
)
from backend.app.models.police import PoliceLocation

logger = logging.getLogger("urbanpulse.adapters.geospatial")

# Bengaluru bounding box (approximate official bounds)
BENGALURU_LAT_MIN = 12.75
BENGALURU_LAT_MAX = 13.20
BENGALURU_LON_MIN = 77.40
BENGALURU_LON_MAX = 77.80


class GeospatialDataAdapter(BaseDataAdapter):
    REQUIRED_FIELDS = ["name", "latitude", "longitude"]

    def __init__(self):
        super().__init__(source_name="EXTERNAL_GEOSPATIAL")

    def fetch(self, source_input: Any = None) -> Any:
        if source_input is None:
            return []
        if isinstance(source_input, str):
            try:
                return json.loads(source_input)
            except Exception as e:
                logger.error(f"[GeospatialAdapter] JSON parse error: {e}")
                return []
        return source_input

    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        normalized = []
        # Support GeoJSON FeatureCollection format
        if isinstance(raw_data, dict) and raw_data.get("type") == "FeatureCollection":
            features = raw_data.get("features", [])
            for feat in features:
                props = feat.get("properties", {})
                geom = feat.get("geometry", {})
                coords = geom.get("coordinates", [None, None])
                lon = coords[0] if len(coords) > 0 else None
                lat = coords[1] if len(coords) > 1 else None
                normalized.append({
                    "name": props.get("name") or props.get("station_name") or "Spatial Point",
                    "latitude": lat,
                    "longitude": lon,
                    "category": props.get("category") or "police_station",
                    "division": props.get("division") or props.get("zone"),
                    "_raw": feat,
                })
            return normalized

        if not isinstance(raw_data, list):
            raw_data = [raw_data] if isinstance(raw_data, dict) else []

        for row in raw_data:
            if not isinstance(row, dict):
                continue

            def parse_float(val: Any) -> Optional[float]:
                try:
                    return float(val) if val is not None else None
                except (ValueError, TypeError):
                    return None

            name = str(row.get("name") or row.get("station_name") or row.get("title") or "").strip()
            lat = parse_float(row.get("latitude") or row.get("lat"))
            lon = parse_float(row.get("longitude") or row.get("lng") or row.get("lon"))
            cat = str(row.get("category") or row.get("type") or "police_station").strip()
            div = str(row.get("division") or row.get("sub_division") or "").strip() or None

            normalized.append({
                "name": name,
                "latitude": lat,
                "longitude": lon,
                "category": cat,
                "division": div,
                "_raw": row,
            })
        return normalized

    def validate(self, normalized_data: List[Dict[str, Any]]) -> ValidationResult:
        if not normalized_data:
            return ValidationResult(
                is_valid=False,
                errors=["Payload contains zero geospatial entities."],
                missing_fields=self.REQUIRED_FIELDS,
                data_quality=DataQualityLevel.UNAVAILABLE,
            )

        errors = []
        warnings = []
        missing_fields = set()

        for idx, row in enumerate(normalized_data):
            if not row.get("name"):
                errors.append(f"Row {idx}: missing feature name")
                missing_fields.add("name")

            lat = row.get("latitude")
            lon = row.get("longitude")
            if lat is None or lon is None:
                errors.append(f"Row {idx}: missing coordinates")
                missing_fields.add("latitude")
                missing_fields.add("longitude")
            else:
                if not (BENGALURU_LAT_MIN <= lat <= BENGALURU_LAT_MAX and BENGALURU_LON_MIN <= lon <= BENGALURU_LON_MAX):
                    warnings.append(f"Row {idx}: coordinates ({lat}, {lon}) outside Bengaluru metropolitan bounding box")

        quality = DataQualityLevel.ACTUAL
        if warnings and not errors:
            quality = DataQualityLevel.ESTIMATED
        elif errors:
            quality = DataQualityLevel.UNAVAILABLE

        return ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            missing_fields=list(missing_fields),
            data_quality=quality,
        )

    def handle_missing(self, normalized_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cleaned = []
        for row in normalized_data:
            item = dict(row)
            if not item.get("division"):
                item["division"] = "Bengaluru City Police Central Command"
            cleaned.append(item)
        return cleaned

    def ingest(self, db: Session, raw_or_cleaned_data: Any) -> AdapterResult:
        normalized = self.normalize(self.fetch(raw_or_cleaned_data))
        validation = self.validate(normalized)
        if not validation.is_valid:
            return AdapterResult(
                source_name=self.source_name,
                status="failed",
                records_processed=0,
                records_failed=len(normalized),
                validation=validation,
                data_quality=validation.data_quality,
                details={"errors": validation.errors[:10]},
            )

        cleaned = self.handle_missing(normalized)
        processed = 0
        failed = 0

        content_bytes = json.dumps(cleaned, sort_keys=True, default=str).encode("utf-8")
        prov_hash = hashlib.sha256(content_bytes).hexdigest()

        for item in cleaned:
            try:
                existing = db.query(PoliceLocation).filter(PoliceLocation.name == item["name"]).first()
                if not existing:
                    import uuid
                    loc = PoliceLocation(
                        location_code=f"geo-{uuid.uuid4().hex[:8]}",
                        name=item["name"],
                        display_name=item["name"],
                        category=item.get("category", "police_station"),
                        latitude=item["latitude"],
                        longitude=item["longitude"],
                    )
                    db.add(loc)
                processed += 1
            except Exception as e:
                logger.error(f"[GeospatialAdapter] Ingestion error: {e}")
                failed += 1

        db.commit()
        return AdapterResult(
            source_name=self.source_name,
            status="success" if failed == 0 else "partial",
            records_processed=processed,
            records_failed=failed,
            validation=validation,
            data_quality=validation.data_quality,
            provenance_hash=prov_hash,
            details={"processed": processed, "failed": failed},
        )
