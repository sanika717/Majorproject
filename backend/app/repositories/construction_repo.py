"""
Construction Repository.
Encapsulates database access for BBMP work orders, ward summaries, and clustering metadata.
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.repositories.base import BaseRepository
from backend.app.models.construction import (
    ConstructionWorkOrder,
    ConstructionWardSummary,
    ConstructionClusterStat,
    ConstructionMeta,
)


class ConstructionRepository(BaseRepository[ConstructionWorkOrder]):
    def __init__(self, db: Session):
        super().__init__(ConstructionWorkOrder, db)

    def get_meta(self, key: str) -> Optional[Any]:
        row = self.db.query(ConstructionMeta).filter(ConstructionMeta.key == key).first()
        return row.value if row else None

    def get_ward_summaries(self) -> List[ConstructionWardSummary]:
        return self.db.query(ConstructionWardSummary).all()

    def get_cluster_stats(self) -> List[ConstructionClusterStat]:
        return self.db.query(ConstructionClusterStat).order_by(ConstructionClusterStat.cluster).all()

    def get_top_wards_by_investment(self, limit: int = 15) -> List[ConstructionWardSummary]:
        return (
            self.db.query(ConstructionWardSummary)
            .order_by(desc(ConstructionWardSummary.total_amount))
            .limit(limit)
            .all()
        )

    def get_top_wards_by_work_orders(self, limit: int = 10) -> List[ConstructionWardSummary]:
        return (
            self.db.query(ConstructionWardSummary)
            .order_by(desc(ConstructionWardSummary.total_work_orders))
            .limit(limit)
            .all()
        )

    def get_by_job_no(self, job_no: str) -> Optional[ConstructionWorkOrder]:
        return self.db.query(ConstructionWorkOrder).filter(ConstructionWorkOrder.job_no == job_no).first()
