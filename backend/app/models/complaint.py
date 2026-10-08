from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum as SaEnum, ForeignKey
from sqlalchemy.orm import relationship
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
    ticket_id = Column(String(32), unique=True, index=True, nullable=False)
    secret_hash = Column(String(64), nullable=True)  # SHA-256 hex digest of tracking secret
    user_id = Column(String(100), index=True, nullable=True)  # Supabase auth user UUID (sub)
    is_identity_hidden = Column(Boolean, default=False, nullable=False)
    pseudonym = Column(String(100), nullable=True)

    category = Column(String(100), nullable=False)
    description = Column(String(2000), nullable=False)  # Max 2000 chars
    location = Column(String(300), nullable=True)
    status = Column(SaEnum(ComplaintStatus), default=ComplaintStatus.SUBMITTED, nullable=False)
    admin_notes = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # One-to-one relationship to separate contact table
    contact_info = relationship("ComplaintContact", back_populates="complaint", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Complaint {self.ticket_id}: {self.category} [{self.status}]>"

class ComplaintContact(Base):
    """Stores sensitive identity/contact data in a separate table from the complaint content."""
    __tablename__ = "complaint_contacts"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    contact = Column(String(100), nullable=True)

    complaint = relationship("Complaint", back_populates="contact_info")
