"""
Electricity Consumption Data Adapter.
Handles ingestion for Bangalore Electricity Supply Company (BESCOM) data,
including sub-division consumption, commercial/domestic tariffs, and kWh normalizations.
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

logger = logging.getLogger("urbanpulse.adapters.electricity")


class ElectricityDataAdapter(BaseDataAdapter):
    REQUIRED_FIELDS = ["sub_division", "consumption_kwh"]

    def __init__(self):
        super().__init__(source_name="BESCOM_ELECTRICITY")

    def fetch(self, source_input: Any = None) -> Any:
        if source_input is None:
            return []
        if isinstance(source_input, str):
            try:
                return json.loads(source_input)
            except Exception as e:
                logger.error(f"[ElectricityAdapter] JSON parse error: {e}")
                return []
        return source_input

    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        normalized = []
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if isinstance(raw_data, dict) else []

        for row in raw_data:
            if not isinstance(row, dict):
                continue

            sub_div = str(row.get("sub_division") or row.get("division") or row.get("area") or "").strip()
            
            def parse_float(val: Any) -> Optional[float]:
                try:
                    return float(val) if val is not None else None
                except (ValueError, TypeError):
                    return None

            kwh = parse_float(row.get("consumption_kwh") or row.get("units_kwh") or row.get("kwh") or row.get("consumption"))
            consumers = row.get("consumer_count") or row.get("consumers") or row.get("meter_count")
            try:
                consumers_count = int(consumers) if consumers is not None else 1
            except (ValueError, TypeError):
                consumers_count = 1

            cat = str(row.get("category") or row.get("tariff_category") or "Mixed Urban").strip()
            month = str(row.get("month") or row.get("billing_cycle") or "").strip() or None

            normalized.append({
                "sub_division": sub_div,
                "consumption_kwh": kwh,
                "consumer_count": consumers_count,
                "category": cat,
                "billing_month": month,
                "_raw": row,
            })
        return normalized

    def validate(self, normalized_data: List[Dict[str, Any]]) -> ValidationResult:
        if not normalized_data:
            return ValidationResult(
                is_valid=False,
                errors=["Payload contains zero electricity consumption records."],
                missing_fields=self.REQUIRED_FIELDS,
                data_quality=DataQualityLevel.UNAVAILABLE,
            )

        errors = []
        warnings = []
        missing_fields = set()

        for idx, row in enumerate(normalized_data):
            if not row.get("sub_division"):
                errors.append(f"Row {idx}: missing sub_division")
                missing_fields.add("sub_division")

            kwh = row.get("consumption_kwh")
            if kwh is None:
                errors.append(f"Row {idx}: missing consumption_kwh")
                missing_fields.add("consumption_kwh")
            elif kwh < 0:
                errors.append(f"Row {idx}: negative electricity consumption ({kwh} kWh)")

            c_count = row.get("consumer_count", 0)
            if c_count < 1:
                warnings.append(f"Row {idx}: consumer count is less than 1")

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
            if not item.get("consumer_count"):
                item["consumer_count"] = 1
            if not item.get("category"):
                item["category"] = "LT-2 Domestic / Commercial"
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
                # NOTE: Electricity data persistence is handled by esg_update/electricity_bescom.py
                # This adapter handles normalization, validation, and category assignment only.
                processed += 1
            except Exception as e:
                logger.error(f"[ElectricityAdapter] Ingestion error: {e}")
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
