from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Enum as SaEnum, ForeignKey, inspect, text
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

class ComplaintPriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

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
    ward = Column(String(100), nullable=True)
    
    priority = Column(String(50), default=ComplaintPriority.MEDIUM.value, nullable=False)
    department = Column(String(150), nullable=True)
    
    # Quantitative Prioritization Factors
    severity_level = Column(Integer, default=2, nullable=False)          # 1 (Minor) to 5 (Critical Emergency)
    public_safety_impact = Column(Boolean, default=False, nullable=False) # True (+5) / False (0)
    affected_area_impact = Column(Integer, default=2, nullable=False)    # 1 (Spot) to 5 (Arterial/Ward-wide)
    priority_score = Column(Integer, default=5, nullable=False)          # Calculated composite priority score

    status = Column(SaEnum(ComplaintStatus), default=ComplaintStatus.SUBMITTED, nullable=False)
    admin_notes = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # One-to-one relationship to separate contact table (Strict Privacy Protection)
    contact_info = relationship("ComplaintContact", back_populates="complaint", uselist=False, cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Complaint {self.ticket_id}: {self.category} [{self.status}] Pri:{self.priority}>"

class ComplaintContact(Base):
    """Stores sensitive identity/contact data in a separate table from the complaint content."""
    __tablename__ = "complaint_contacts"

    id = Column(Integer, primary_key=True, index=True)
    complaint_id = Column(Integer, ForeignKey("complaints.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=True)
    contact = Column(String(100), nullable=True)

    complaint = relationship("Complaint", back_populates="contact_info")


def ensure_complaint_columns(target_engine):
    """
    Ensures that newly introduced columns exist in the PostgreSQL / SQLite complaints table.
    Safe and idempotent migration without dropping any existing records.
    """
    try:
        insp = inspect(target_engine)
        if "complaints" not in insp.get_table_names():
            Base.metadata.create_all(bind=target_engine)
            return

        existing_cols = {c["name"] for c in insp.get_columns("complaints")}
        with target_engine.connect() as conn:
            if "ward" not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN ward VARCHAR(100)"))
            if "priority" not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN priority VARCHAR(50) DEFAULT 'MEDIUM' NOT NULL"))
            if "department" not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN department VARCHAR(150)"))
            if "severity_level" not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN severity_level INTEGER DEFAULT 2 NOT NULL"))
            if "public_safety_impact" not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN public_safety_impact BOOLEAN DEFAULT FALSE NOT NULL"))
            if "affected_area_impact" not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN affected_area_impact INTEGER DEFAULT 2 NOT NULL"))
            if "priority_score" not in existing_cols:
                conn.execute(text("ALTER TABLE complaints ADD COLUMN priority_score INTEGER DEFAULT 5 NOT NULL"))
            conn.commit()
    except Exception as e:
        print(f"[UrbanPulse] Note on complaint schema migration: {e}")

