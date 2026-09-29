from sqlalchemy import Column, Integer, String, Text, DateTime, Enum as SaEnum
from datetime import datetime
import enum
from backend.app.db.session import Base

class ComplaintStatus(str, enum.Enum):
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"

class Complaint(Base):
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(20), unique=True, index=True, nullable=False)
    category = Column(String(100), nullable=False)
    description = Column(Text, nullable=False)
    location = Column(String(300), nullable=True)
    name = Column(String(100), nullable=True)
    contact = Column(String(100), nullable=True)
    status = Column(SaEnum(ComplaintStatus), default=ComplaintStatus.SUBMITTED, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    admin_notes = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Complaint {self.ticket_id}: {self.category} [{self.status}]>"
