import base64
import hashlib
import io
import os
import secrets
import string
from datetime import datetime
from typing import List, Optional, Dict, Any
from PIL import Image
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from backend.app.models.complaint import Complaint, ComplaintContact, ComplaintStatus, ComplaintPriority
from backend.app.schemas.complaint import ComplaintSubmit, ComplaintStatusUpdate, ComplaintAdminUpdate

DEFAULT_DEPARTMENT_BY_CATEGORY = {
    "Roads & Potholes": "BBMP Roads Infrastructure",
    "Drainage & Flooding": "BBMP Stormwater Drains",
    "Water Supply & Sewage": "BWSSB (Water Supply & Sewerage Board)",
    "Street Lights": "BESCOM (Electricity Supply)",
    "Garbage & Sanitation": "BBMP Solid Waste Management",
    "Ongoing Construction Work": "BBMP Town Planning & Engineering",
    "Safety & Policing": "Bengaluru City Police",
    "Other": "BBMP Civic Administration"
}

def calculate_priority_score(severity: int, public_safety: bool, area_impact: int) -> tuple[int, ComplaintPriority]:
    """
    Computes priority based on objective criteria:
    - severity: 1 (cosmetic/minor) to 5 (critical danger) -> weight 2.0
    - public_safety: True (+5 pts), False (0 pts)
    - affected_area_impact: 1 (spot) to 5 (ward/arterial) -> weight 1.5
    """
    sev = max(1, min(5, int(severity or 2)))
    area = max(1, min(5, int(area_impact or 2)))
    safety_pts = 5 if public_safety else 0
    raw = (sev * 2.0) + safety_pts + (area * 1.5)
    score = int(raw + 0.5)
    
    if score >= 15:
        pri = ComplaintPriority.CRITICAL
    elif score >= 11:
        pri = ComplaintPriority.HIGH
    elif score >= 7:
        pri = ComplaintPriority.MEDIUM
    else:
        pri = ComplaintPriority.LOW
    return score, pri

def _generate_ticket_id() -> str:
    """Generate a unique tracking ID like UP-2026-XA7B9C"""
    suffix = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
    return f"UP-{datetime.utcnow().year}-{suffix}"

def _generate_pseudonym() -> str:
    animals = ["Elephant", "Tiger", "Peacock", "Leopard", "Bison", "Eagle", "Falcon", "Otter"]
    colors = ["Amber", "Silver", "Emerald", "Indigo", "Azure", "Crimson", "Golden", "Sapphire"]
    num = secrets.randbelow(900) + 100
    return f"Citizen {secrets.choice(colors)} {secrets.choice(animals)} #{num}"

def strip_exif_image(base64_data: str) -> Optional[str]:
    """
    Strips EXIF metadata from base64 image data and returns clean JPEG/PNG base64.
    Protects user location privacy from embedded EXIF GPS tags.
    """
    if not base64_data:
        return None
    try:
        if "," in base64_data:
            base64_data = base64_data.split(",", 1)[1]
        image_bytes = base64.b64decode(base64_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Strip EXIF by copying raw image pixels without metadata
        data = list(image.getdata())
        image_without_exif = Image.new(image.mode, image.size)
        image_without_exif.putdata(data)
        
        output_io = io.BytesIO()
        fmt = image.format if image.format in ["JPEG", "PNG", "WEBP"] else "JPEG"
        image_without_exif.save(output_io, format=fmt)
        clean_bytes = output_io.getvalue()
        return "data:image/jpeg;base64," + base64.b64encode(clean_bytes).decode("utf-8")
    except Exception:
        # If processing fails, do not store unverified image
        return None

class ComplaintService:
    @staticmethod
    def submit_complaint(
        db: Session,
        data: ComplaintSubmit,
        current_user: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Creates complaint with real database persistence.
        - Anonymous or logged in
        - Secret token generated via secrets.token_urlsafe(24), stored as SHA-256
        - Contact data isolated into complaint_contacts
        - No IP or User-Agent stored
        - Pseudonym assigned if hide_identity is True
        - Automatically computes objective priority score and assigns responsible department
        """
        ticket_id = _generate_ticket_id()
        while db.query(Complaint).filter(Complaint.ticket_id == ticket_id).first():
            ticket_id = _generate_ticket_id()

        # Generate 24-character urlsafe secret
        tracking_secret = secrets.token_urlsafe(24)
        secret_hash = hashlib.sha256(tracking_secret.encode("utf-8")).hexdigest()

        user_id = None
        if current_user:
            user_id = current_user.get("sub") or current_user.get("id")

        is_identity_hidden = bool(data.hide_identity)
        pseudonym = _generate_pseudonym() if is_identity_hidden else None

        # Clean image EXIF if provided
        clean_img = strip_exif_image(data.image_base64) if data.image_base64 else None

        # Department assignment
        assigned_dept = data.department or DEFAULT_DEPARTMENT_BY_CATEGORY.get(data.category, "BBMP Civic Administration")

        # Priority calculation based on severity, public safety, and area impact
        sev = data.severity_level if data.severity_level is not None else 2
        safety = bool(data.public_safety_impact)
        area = data.affected_area_impact if data.affected_area_impact is not None else 2
        pri_score, priority_enum = calculate_priority_score(sev, safety, area)

        # Extract ward if specified or infer from location string
        ward_val = data.ward
        if not ward_val and data.location:
            loc_lower = data.location.lower()
            if "ward" in loc_lower:
                parts = data.location.split(",")
                for p in parts:
                    if "ward" in p.lower():
                        ward_val = p.strip()
                        break

        complaint = Complaint(
            ticket_id=ticket_id,
            secret_hash=secret_hash,
            user_id=user_id,
            is_identity_hidden=is_identity_hidden,
            pseudonym=pseudonym,
            category=data.category,
            description=data.description,
            location=data.location,
            ward=ward_val,
            priority=priority_enum.value,
            department=assigned_dept,
            severity_level=sev,
            public_safety_impact=safety,
            affected_area_impact=area,
            priority_score=pri_score,
            status=ComplaintStatus.SUBMITTED,
            image_url=clean_img
        )
        db.add(complaint)
        db.flush()

        # Store contact data separately for strict privacy protection
        if data.name or data.contact:
            contact_entry = ComplaintContact(
                complaint_id=complaint.id,
                name=data.name,
                contact=data.contact
            )
            db.add(contact_entry)

        db.commit()
        db.refresh(complaint)

        return {
            "id": complaint.id,
            "ticket_id": complaint.ticket_id,
            "tracking_secret": tracking_secret,
            "category": complaint.category,
            "description": complaint.description,
            "location": complaint.location,
            "ward": complaint.ward,
            "priority": complaint.priority,
            "department": complaint.department,
            "severity_level": complaint.severity_level,
            "public_safety_impact": complaint.public_safety_impact,
            "affected_area_impact": complaint.affected_area_impact,
            "priority_score": complaint.priority_score,
            "status": complaint.status,
            "created_at": complaint.created_at,
            "message": "Complaint submitted successfully. Save your tracking secret to check status."
        }

    @staticmethod
    def get_by_ticket_and_secret(db: Session, ticket_id: str, secret: str) -> Optional[Complaint]:
        """
        Tracks a complaint using BOTH ticket ID and secret code.
        Verifies SHA-256 hash. SQL injection safe via SQLAlchemy parameters.
        """
        incoming_hash = hashlib.sha256(secret.strip().encode("utf-8")).hexdigest()
        clean_ticket = ticket_id.strip().upper()
        complaint = db.query(Complaint).filter(
            Complaint.ticket_id == clean_ticket,
            Complaint.secret_hash == incoming_hash
        ).first()
        return complaint

    @staticmethod
    def get_by_ticket(db: Session, ticket_id: str) -> Optional[Complaint]:
        clean_ticket = ticket_id.strip().upper()
        return db.query(Complaint).filter(Complaint.ticket_id == clean_ticket).first()

    @staticmethod
    def get_user_complaints(db: Session, user_id: str, limit: int = 50, offset: int = 0) -> List[Complaint]:
        """Returns complaints owned by the specific logged-in user."""
        return db.query(Complaint).filter(
            Complaint.user_id == str(user_id)
        ).order_by(desc(Complaint.created_at)).offset(offset).limit(limit).all()

    @staticmethod
    def get_all_admin(
        db: Session,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        department: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Complaint]:
        """Authority/Admin listing of all complaints with comprehensive filtering."""
        q = db.query(Complaint)
        if status:
            try:
                status_enum = ComplaintStatus(status.upper())
                q = q.filter(Complaint.status == status_enum)
            except ValueError:
                pass
        if priority:
            clean_pri = priority.upper()
            q = q.filter(Complaint.priority == clean_pri)
        if department:
            q = q.filter(Complaint.department.ilike(f"%{department.strip()}%"))
        if search:
            s = f"%{search.strip()}%"
            q = q.filter(or_(
                Complaint.ticket_id.ilike(s),
                Complaint.category.ilike(s),
                Complaint.description.ilike(s),
                Complaint.location.ilike(s),
                Complaint.ward.ilike(s)
            ))
        return q.order_by(desc(Complaint.created_at)).offset(offset).limit(limit).all()

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
    def admin_review_complaint(db: Session, ticket_id: str, update: ComplaintAdminUpdate) -> Optional[Complaint]:
        """
        Complete authority review action:
        - updates status
        - assigns/reassigns department
        - updates severity, public safety impact, and area impact
        - recalculates or sets priority
        - adds/updates official remarks
        """
        complaint = ComplaintService.get_by_ticket(db, ticket_id)
        if not complaint:
            return None

        if update.status is not None:
            complaint.status = update.status
        if update.department is not None:
            complaint.department = update.department.strip()
        if update.admin_notes is not None:
            complaint.admin_notes = update.admin_notes

        # Re-evaluate priority if severity or impacts updated
        recalc_priority = False
        if update.severity_level is not None:
            complaint.severity_level = update.severity_level
            recalc_priority = True
        if update.public_safety_impact is not None:
            complaint.public_safety_impact = update.public_safety_impact
            recalc_priority = True
        if update.affected_area_impact is not None:
            complaint.affected_area_impact = update.affected_area_impact
            recalc_priority = True

        if recalc_priority and update.priority is None:
            score, pri = calculate_priority_score(
                complaint.severity_level,
                complaint.public_safety_impact,
                complaint.affected_area_impact
            )
            complaint.priority_score = score
            complaint.priority = pri.value
        elif update.priority is not None:
            complaint.priority = update.priority.value

        complaint.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(complaint)
        return complaint

    @staticmethod
    def get_stats(db: Session) -> Dict[str, Any]:
        """
        Computes real-time statistics strictly from existing PostgreSQL database records.
        Returns empty / 0 counts honestly when no records exist.
        """
        total = db.query(Complaint).count()
        by_status = {}
        for s in ComplaintStatus:
            by_status[s.value] = db.query(Complaint).filter(Complaint.status == s).count()
        
        by_priority = {}
        for p in ComplaintPriority:
            by_priority[p.value] = db.query(Complaint).filter(Complaint.priority == p.value).count()

        by_category = {}
        rows = db.query(Complaint.category).all()
        for (cat,) in rows:
            by_category[cat] = by_category.get(cat, 0) + 1

        by_department = {}
        dept_rows = db.query(Complaint.department).filter(Complaint.department.isnot(None)).all()
        for (dept,) in dept_rows:
            if dept:
                by_department[dept] = by_department.get(dept, 0) + 1

        return {
            "total": total,
            "by_status": by_status,
            "by_priority": by_priority,
            "by_category": by_category,
            "by_department": by_department
        }

    @staticmethod
    def get_all_public(db: Session, limit: int = 15, offset: int = 0) -> list:
        """
        Public feed: returns real database records with identity strictly protected.
        No name, contact, user_id, or secret_hash is ever exposed.
        Description is truncated to 200 chars for public feed cards.
        """
        complaints = db.query(Complaint).order_by(
            desc(Complaint.created_at)
        ).offset(offset).limit(limit).all()

        result = []
        for c in complaints:
            result.append({
                "ticket_id":            c.ticket_id,
                "category":             c.category,
                "description":          (c.description or "")[:200],
                "location":             c.location,
                "ward":                 c.ward,
                "priority":             c.priority,
                "department":           c.department,
                "severity_level":       c.severity_level,
                "public_safety_impact": c.public_safety_impact,
                "affected_area_impact": c.affected_area_impact,
                "priority_score":       c.priority_score,
                "status":               c.status.value if hasattr(c.status, "value") else str(c.status),
                "created_at":           c.created_at.isoformat() if c.created_at else None,
                "updated_at":           c.updated_at.isoformat() if c.updated_at else None,
                "admin_notes":          c.admin_notes,
            })
        return result

    @staticmethod
    def format_for_viewer(complaint: Complaint, viewer_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Formats complaint ensuring anonymity & pseudonymity rules.
        Complainant contact info is NEVER exposed.
        """
        is_admin = viewer_user and (viewer_user.get("role") or "").lower() == "admin"
        viewer_id = viewer_user.get("sub") if viewer_user else None
        is_owner = viewer_id and str(viewer_id) == str(complaint.user_id)

        display_name = None
        if complaint.is_identity_hidden:
            display_name = complaint.pseudonym or "Anonymous Citizen"
        else:
            if is_owner and complaint.contact_info and complaint.contact_info.name:
                display_name = complaint.contact_info.name
            elif is_owner and viewer_user and viewer_user.get("email"):
                display_name = viewer_user.get("email")
            else:
                display_name = "Anonymous Citizen"

        return {
            "id":                   complaint.id,
            "ticket_id":            complaint.ticket_id,
            "category":             complaint.category,
            "description":          complaint.description,
            "location":             complaint.location,
            "ward":                 complaint.ward,
            "priority":             complaint.priority,
            "department":           complaint.department,
            "severity_level":       complaint.severity_level,
            "public_safety_impact": complaint.public_safety_impact,
            "affected_area_impact": complaint.affected_area_impact,
            "priority_score":       complaint.priority_score,
            "name":                 display_name,
            "status":               complaint.status,
            "created_at":           complaint.created_at,
            "updated_at":           complaint.updated_at,
            "admin_notes":          complaint.admin_notes,
            "image_url":            complaint.image_url
        }
