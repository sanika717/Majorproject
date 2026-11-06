"""
ESG Repository.
Encapsulates database access for Air Quality, Lake Water, Energy, and Provenance audit records.
Operates on actual ESG ORM models.
"""

from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.repositories.base import BaseRepository
from backend.app.models.esg import (
    EsgAirStation,
    EsgAirLive,
    EsgWaterReading,
    EsgElectricity,
    EsgRecalcLog,
)


class EsgRepository(BaseRepository[EsgAirStation]):
    def __init__(self, db: Session):
        super().__init__(EsgAirStation, db)

    def get_latest_air_live_readings(self, limit: int = 10) -> List[EsgAirLive]:
        return (
            self.db.query(EsgAirLive)
            .order_by(desc(EsgAirLive.id))
            .limit(limit)
            .all()
        )

    def get_water_records(self, limit: int = 50) -> List[EsgWaterReading]:
        return self.db.query(EsgWaterReading).limit(limit).all()

    def get_energy_records(self, limit: int = 50) -> List[EsgElectricity]:
        return self.db.query(EsgElectricity).limit(limit).all()

    def get_latest_recalc(self) -> Optional[EsgRecalcLog]:
        return (
            self.db.query(EsgRecalcLog)
            .order_by(desc(EsgRecalcLog.triggered_at))
            .first()
        )
