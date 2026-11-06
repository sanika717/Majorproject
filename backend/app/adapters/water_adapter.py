"""
Water Pollution & Lake Quality Data Adapter.
Handles ingestion for Karnataka State Pollution Control Board (KSPCB) / MINARS
water quality monitoring across Bengaluru lakes and water bodies.
Validates Dissolved Oxygen (DO), Biochemical Oxygen Demand (BOD), pH, and classifies CPCB Water Quality Classes (A-E).
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

logger = logging.getLogger("urbanpulse.adapters.water")


class WaterQualityAdapter(BaseDataAdapter):
    REQUIRED_FIELDS = ["station_name", "body_name"]

    def __init__(self):
        super().__init__(source_name="KSPCB_MINARS_WATER")

    def fetch(self, source_input: Any = None) -> Any:
        if source_input is None:
            return []
        if isinstance(source_input, str):
            try:
                return json.loads(source_input)
            except Exception as e:
                logger.error(f"[WaterAdapter] JSON parse error: {e}")
                return []
        return source_input

    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        normalized = []
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

            stn = str(row.get("station_name") or row.get("station_id") or row.get("sampling_point") or "").strip()
            body = str(row.get("body_name") or row.get("lake_name") or row.get("water_body") or stn).strip()

            do_val = parse_float(row.get("dissolved_oxygen") or row.get("do") or row.get("do_mg_l"))
            bod_val = parse_float(row.get("bod") or row.get("bod_mg_l"))
            ph_val = parse_float(row.get("ph"))

            # Derive CPCB Class deterministically: Class A/B/C/D/E
            water_class = str(row.get("water_class") or row.get("class") or "").strip().upper()
            if not water_class:
                if bod_val is not None:
                    if bod_val <= 2.0:
                        water_class = "A"
                    elif bod_val <= 3.0:
                        water_class = "B"
                    elif bod_val <= 6.0:
                        water_class = "C"
                    elif bod_val <= 10.0:
                        water_class = "D"
                    else:
                        water_class = "E"
                else:
                    water_class = "D"  # fallback default for unclassified urban lakes

            normalized.append({
                "station_name": stn,
                "body_name": body,
                "station_code": str(row.get("station_code") or "").strip() or None,
                "dissolved_oxygen": do_val,
                "bod": bod_val,
                "ph": ph_val,
                "water_class": water_class,
                "sampling_date": str(row.get("sampling_date") or row.get("date") or "").strip() or None,
                "_raw": row,
            })
        return normalized

    def validate(self, normalized_data: List[Dict[str, Any]]) -> ValidationResult:
        if not normalized_data:
            return ValidationResult(
                is_valid=False,
                errors=["Payload contains zero water quality records."],
                missing_fields=self.REQUIRED_FIELDS,
                data_quality=DataQualityLevel.UNAVAILABLE,
            )

        errors = []
        warnings = []
        missing_fields = set()

        for idx, row in enumerate(normalized_data):
            if not row.get("station_name") and not row.get("body_name"):
                errors.append(f"Row {idx}: missing both station_name and body_name")
                missing_fields.add("station_name")

            ph = row.get("ph")
            if ph is not None and not (0.0 <= ph <= 14.0):
                errors.append(f"Row {idx}: pH {ph} outside chemical range 0-14")

            do_val = row.get("dissolved_oxygen")
            if do_val is not None and (do_val < 0.0 or do_val > 25.0):
                warnings.append(f"Row {idx}: dissolved oxygen {do_val} mg/L unusually high")

            bod = row.get("bod")
            if bod is not None and bod < 0.0:
                errors.append(f"Row {idx}: negative BOD ({bod})")

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
            if not item.get("body_name") and item.get("station_name"):
                item["body_name"] = item["station_name"]
            if not item.get("station_name") and item.get("body_name"):
                item["station_name"] = item["body_name"]
            if item.get("dissolved_oxygen") is None:
                item["dissolved_oxygen_estimated"] = True
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
                # NOTE: Water quality persistence is handled by esg_update/file_sources.py
                # This adapter handles normalization, validation, and class derivation only.
                processed += 1
            except Exception as e:
                logger.error(f"[WaterAdapter] Ingestion error: {e}")
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
