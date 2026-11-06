"""
Crime Datasets Data Adapter.
Handles retrieval, format normalization, validation, and missing value processing
for Bengaluru Police historical crime reports and D47 crime incident records.
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
from backend.app.models.crime import CrimeRecord

logger = logging.getLogger("urbanpulse.adapters.crime")


class CrimeDataAdapter(BaseDataAdapter):
    REQUIRED_FIELDS = ["category", "year", "total_cases"]

    def __init__(self):
        super().__init__(source_name="CRIME_STATISTICS")

    def fetch(self, source_input: Any = None) -> Any:
        if source_input is None:
            return []
        if isinstance(source_input, str):
            try:
                return json.loads(source_input)
            except Exception as e:
                logger.error(f"[CrimeAdapter] JSON parsing error: {e}")
                return []
        return source_input

    def normalize(self, raw_data: Any) -> List[Dict[str, Any]]:
        normalized = []
        if not isinstance(raw_data, list):
            raw_data = [raw_data] if isinstance(raw_data, dict) else []

        for row in raw_data:
            if not isinstance(row, dict):
                continue

            cat = str(row.get("category") or row.get("crime_type") or row.get("offense") or "").strip()
            year_raw = row.get("year") or row.get("crime_year")
            try:
                year = int(year_raw) if year_raw is not None else None
            except (ValueError, TypeError):
                year = None

            total_raw = row.get("total_cases") or row.get("total") or row.get("cases_reported") or row.get("incidents")
            try:
                total_cases = int(total_raw) if total_raw is not None else 0
            except (ValueError, TypeError):
                total_cases = 0

            fatal_raw = row.get("fatal_cases") or row.get("fatal") or row.get("deaths")
            try:
                fatal_cases = int(fatal_raw) if fatal_raw is not None else 0
            except (ValueError, TypeError):
                fatal_cases = 0

            non_fatal_raw = row.get("non_fatal_cases") or row.get("non_fatal")
            try:
                non_fatal_cases = int(non_fatal_raw) if non_fatal_raw is not None else max(0, total_cases - fatal_cases)
            except (ValueError, TypeError):
                non_fatal_cases = max(0, total_cases - fatal_cases)

            station = str(row.get("police_station") or row.get("station") or row.get("ps_name") or "").strip() or None

            normalized.append({
                "category": cat,
                "year": year,
                "total_cases": total_cases,
                "fatal_cases": fatal_cases,
                "non_fatal_cases": non_fatal_cases,
                "police_station": station,
                "_raw": row,
            })
        return normalized

    def validate(self, normalized_data: List[Dict[str, Any]]) -> ValidationResult:
        if not normalized_data:
            return ValidationResult(
                is_valid=False,
                errors=["Payload contains zero crime records."],
                missing_fields=self.REQUIRED_FIELDS,
                data_quality=DataQualityLevel.UNAVAILABLE,
            )

        errors = []
        warnings = []
        missing_fields = set()

        for idx, row in enumerate(normalized_data):
            if not row.get("category"):
                errors.append(f"Row {idx}: missing crime category")
                missing_fields.add("category")

            year = row.get("year")
            if year is None:
                errors.append(f"Row {idx}: missing or invalid year")
                missing_fields.add("year")
            elif year < 2000 or year > 2030:
                warnings.append(f"Row {idx}: year {year} outside expected range (2000-2030)")

            tot = row.get("total_cases", 0)
            fat = row.get("fatal_cases", 0)
            if tot < 0 or fat < 0:
                errors.append(f"Row {idx}: negative case counts detected")
            if fat > tot:
                warnings.append(f"Row {idx}: fatal cases ({fat}) exceeds total cases ({tot})")

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
            if item.get("fatal_cases") is None:
                item["fatal_cases"] = 0
            if item.get("total_cases") is None:
                item["total_cases"] = item["fatal_cases"] + (item.get("non_fatal_cases") or 0)
            if item.get("non_fatal_cases") is None:
                item["non_fatal_cases"] = max(0, item["total_cases"] - item["fatal_cases"])
            if not item.get("police_station"):
                item["police_station"] = "Bengaluru City Police (Jurisdiction-Wide)"
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
                # CrimeRecord.year is a String type in the model
                existing = (
                    db.query(CrimeRecord)
                    .filter(
                        CrimeRecord.category == item["category"],
                        CrimeRecord.year == str(item["year"]),
                    )
                    .first()
                )
                if not existing:
                    new_rec = CrimeRecord(
                        category=item["category"],
                        year=str(item["year"]),
                    )
                    db.add(new_rec)
                processed += 1
            except Exception as e:
                logger.error(f"[CrimeAdapter] Ingestion error: {e}")
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
