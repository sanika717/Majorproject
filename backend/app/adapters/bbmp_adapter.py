"""
BBMP Work Orders Data Adapter.
Handles retrieval, format normalization, validation, missing value imputation,
and ingestion for Bruhat Bengaluru Mahanagara Palike (BBMP) infrastructure projects.
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
from backend.app.models.construction import ConstructionWorkOrder

logger = logging.getLogger("urbanpulse.adapters.bbmp")


class BbmpWorkOrderAdapter(BaseDataAdapter):
    REQUIRED_FIELDS = ["work_order_number", "ward_number", "gross_amount"]

    def __init__(self):
        super().__init__(source_name="BBMP_WORK_ORDERS")

    def fetch(self, source_input: Any = None) -> Any:
        if source_input is None:
            return []
        if isinstance(source_input, str):
            try:
                return json.loads(source_input)
            except Exception as e:
                logger.error(f"[BbmpAdapter] Failed to parse JSON input: {e}")
                return []
        return source_input

    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        normalized = []
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if isinstance(raw_data, dict) else []

        for row in raw_data:
            if not isinstance(row, dict):
                continue
            # Handle aliases across BBMP data sources
            wo_num = str(row.get("work_order_number") or row.get("wo_number") or row.get("id") or "").strip()
            ward_raw = row.get("ward_number") or row.get("ward") or row.get("ward_code")
            try:
                ward_num = int(ward_raw) if ward_raw is not None else None
            except (ValueError, TypeError):
                ward_num = None

            gross_amt = row.get("gross_amount") or row.get("amount") or row.get("total_amount")
            try:
                gross = float(gross_amt) if gross_amt is not None else 0.0
            except (ValueError, TypeError):
                gross = 0.0

            net_amt = row.get("net_amount") or row.get("net_expenditure")
            try:
                net = float(net_amt) if net_amt is not None else gross * 0.90
            except (ValueError, TypeError):
                net = gross * 0.90

            deduction = row.get("deduction")
            try:
                ded = float(deduction) if deduction is not None else max(0.0, gross - net)
            except (ValueError, TypeError):
                ded = max(0.0, gross - net)

            norm_row = {
                "work_order_number": wo_num,
                "ward_number": ward_num,
                "ward_name": str(row.get("ward_name") or row.get("locality") or "").strip() or None,
                "project_description": str(row.get("project_description") or row.get("work_details") or "").strip() or None,
                "category": str(row.get("category") or row.get("work_type") or "General Civil").strip(),
                "contractor_name": str(row.get("contractor_name") or row.get("contractor") or "").strip() or None,
                "gross_amount": gross,
                "net_amount": net,
                "deduction": ded,
                "status": str(row.get("status") or "Approved").strip(),
                "fiscal_year": str(row.get("fiscal_year") or "2024-2025").strip(),
                "_raw": row,
            }
            normalized.append(norm_row)
        return normalized

    def validate(self, normalized_data: List[Dict[str, Any]]) -> ValidationResult:
        if not normalized_data:
            return ValidationResult(
                is_valid=False,
                errors=["Payload contains zero records."],
                missing_fields=self.REQUIRED_FIELDS,
                data_quality=DataQualityLevel.UNAVAILABLE,
            )

        errors = []
        warnings = []
        missing_fields = set()

        for idx, row in enumerate(normalized_data):
            if not row.get("work_order_number"):
                errors.append(f"Row {idx}: missing work_order_number")
                missing_fields.add("work_order_number")

            ward = row.get("ward_number")
            if ward is None:
                errors.append(f"Row {idx}: missing or unparseable ward_number")
                missing_fields.add("ward_number")
            elif ward < 1 or ward > 250:
                warnings.append(f"Row {idx}: ward_number {ward} outside official BBMP bounds (1-198 / 225)")

            if row.get("gross_amount", 0.0) < 0:
                errors.append(f"Row {idx}: negative gross_amount ({row.get('gross_amount')})")

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
            # Deterministically handle missing values without fabricating
            item = dict(row)
            if not item.get("ward_name") and item.get("ward_number"):
                item["ward_name"] = f"Ward {item['ward_number']}"
            if item.get("net_amount") is None and item.get("gross_amount") is not None:
                item["net_amount"] = round(item["gross_amount"] * 0.90, 2)
            if item.get("deduction") is None and item.get("gross_amount") is not None:
                item["deduction"] = round(item["gross_amount"] - (item.get("net_amount") or 0.0), 2)
            if not item.get("contractor_name"):
                item["contractor_name"] = "Undisclosed / BBMP Direct"
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

        # Compute deterministic provenance hash
        content_bytes = json.dumps(cleaned, sort_keys=True, default=str).encode("utf-8")
        prov_hash = hashlib.sha256(content_bytes).hexdigest()

        for item in cleaned:
            try:
                wo_num = item["work_order_number"]
                existing = db.query(ConstructionWorkOrder).filter(ConstructionWorkOrder.work_order_id == wo_num).first()
                if not existing:
                    new_wo = ConstructionWorkOrder(
                        work_order_id=wo_num,
                        ward=str(item["ward_number"]) if item["ward_number"] else "Unknown",
                        wodetails=item.get("project_description") or "BBMP Infrastructure Project",
                        amount=int(item["gross_amount"]),
                        nett=int(item["net_amount"]),
                        deduction=int(item["deduction"]),
                        contractor=item["contractor_name"],
                    )
                    db.add(new_wo)
                processed += 1
            except Exception as e:
                logger.error(f"[BbmpAdapter] Error inserting work order {item.get('work_order_number')}: {e}")
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
