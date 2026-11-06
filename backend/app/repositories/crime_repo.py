"""
Crime Repository.
Encapsulates database access for Crime records, historical trends, and risk formulas.
"""

from typing import List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.repositories.base import BaseRepository
from backend.app.models.crime import (
    CrimeHistorical,
    CrimeRecord,
    CrimeCategoryYearSummary,
    CrimeMeta,
)


class CrimeRepository(BaseRepository[CrimeRecord]):
    def __init__(self, db: Session):
        super().__init__(CrimeRecord, db)

    def get_historical(self) -> Optional[CrimeHistorical]:
        return self.db.query(CrimeHistorical).first()

    def get_meta(self, key: str) -> Optional[Any]:
        row = self.db.query(CrimeMeta).filter(CrimeMeta.key == key).first()
        return row.value if row else None

    def get_yearly_breakdown(self) -> List[CrimeCategoryYearSummary]:
        return (
            self.db.query(CrimeCategoryYearSummary)
            .order_by(desc(CrimeCategoryYearSummary.year))
            .all()
        )

    def get_records_by_category(self, category: str) -> List[CrimeRecord]:
        return self.db.query(CrimeRecord).filter(CrimeRecord.crime_category == category).all()
