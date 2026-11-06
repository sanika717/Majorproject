"""
Complaint Repository.
Encapsulates database queries and transactions for public grievances, audit logs, and status transitions.
"""

from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.repositories.base import BaseRepository
from backend.app.models.complaint import Complaint, ComplaintEvent, ComplaintAttachment


class ComplaintRepository(BaseRepository[Complaint]):
    def __init__(self, db: Session):
        super().__init__(Complaint, db)

    def get_by_ticket_number(self, ticket_number: str) -> Optional[Complaint]:
        return self.db.query(Complaint).filter(Complaint.ticket_number == ticket_number).first()

    def get_filtered(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        ward: Optional[int] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> Tuple[List[Complaint], int]:
        q = self.db.query(Complaint)
        if status:
            q = q.filter(Complaint.status == status)
        if category:
            q = q.filter(Complaint.category == category)
        if ward:
            q = q.filter(Complaint.ward == ward)
        total = q.count()
        items = q.order_by(desc(Complaint.created_at)).offset(offset).limit(limit).all()
        return items, total

    def add_event(self, event: ComplaintEvent) -> ComplaintEvent:
        self.db.add(event)
        self.db.flush()
        return event

    def get_events(self, complaint_id: int) -> List[ComplaintEvent]:
        return (
            self.db.query(ComplaintEvent)
            .filter(ComplaintEvent.complaint_id == complaint_id)
            .order_by(ComplaintEvent.created_at.asc())
            .all()
        )
