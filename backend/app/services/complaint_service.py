import secrets
import string
from datetime import datetime
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.models.complaint import Complaint, ComplaintStatus
from backend.app.schemas.complaint import ComplaintSubmit, ComplaintStatusUpdate

def _generate_ticket_id() -> str:
    """Generate a unique ticket ID like UP-2026-XA7B9C"""
    suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"UP-{datetime.utcnow().year}-{suffix}"

class ComplaintService:
    @staticmethod
    def submit_complaint(db: Session, data: ComplaintSubmit) -> Complaint:
        ticket_id = _generate_ticket_id()
        # Ensure uniqueness
        while db.query(Complaint).filter(Complaint.ticket_id == ticket_id).first():
            ticket_id = _generate_ticket_id()

        complaint = Complaint(
            ticket_id=ticket_id,
            category=data.category,
            description=data.description,
            location=data.location,
            name=data.name,
            contact=data.contact,
            status=ComplaintStatus.SUBMITTED
        )
        db.add(complaint)
        db.commit()
        db.refresh(complaint)
        return complaint

    @staticmethod
    def get_all(db: Session, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Complaint]:
        q = db.query(Complaint)
        if status:
            try:
                q = q.filter(Complaint.status == ComplaintStatus(status.upper()))
            except ValueError:
                pass
        return q.order_by(desc(Complaint.created_at)).offset(offset).limit(limit).all()

    @staticmethod
    def get_by_ticket(db: Session, ticket_id: str) -> Optional[Complaint]:
        return db.query(Complaint).filter(Complaint.ticket_id == ticket_id.upper()).first()

    @staticmethod
    def update_status(db: Session, ticket_id: str, update: ComplaintStatusUpdate) -> Optional[Complaint]:
        complaint = ComplaintService.get_by_ticket(db, ticket_id)
        if not complaint:
            return None
        complaint.status = update.status
        if update.admin_notes is not None:
            complaint.admin_notes = update.admin_notes
        complaint.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(complaint)
        return complaint

    @staticmethod
    def get_stats(db: Session) -> Dict[str, Any]:
        total = db.query(Complaint).count()
        by_status = {}
        for s in ComplaintStatus:
            by_status[s.value] = db.query(Complaint).filter(Complaint.status == s).count()
        by_category = {}
        rows = db.query(Complaint.category).all()
        for (cat,) in rows:
            by_category[cat] = by_category.get(cat, 0) + 1
        return {
            "total": total,
            "by_status": by_status,
            "by_category": by_category
        }
