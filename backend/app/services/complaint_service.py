import base64
import hashlib
import io
import os
import secrets
import string
from datetime import datetime
from typing import List, Optional, Dict, Any
from PIL import Image, ImageOps
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.app.models.complaint import Complaint, ComplaintContact, ComplaintStatus
from backend.app.schemas.complaint import ComplaintSubmit, ComplaintStatusUpdate

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
        Creates complaint.
        - Anonymous or logged in
        - Secret token generated via secrets.token_urlsafe(24), stored as SHA-256
        - Contact data isolated into complaint_contacts
        - No IP or User-Agent stored
        - Pseudonym assigned if hide_identity is True
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

        complaint = Complaint(
            ticket_id=ticket_id,
            secret_hash=secret_hash,
            user_id=user_id,
            is_identity_hidden=is_identity_hidden,
            pseudonym=pseudonym,
            category=data.category,
            description=data.description,
            location=data.location,
            status=ComplaintStatus.SUBMITTED,
            image_url=clean_img
        )
        db.add(complaint)
        db.flush()

        # Store contact data separately
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
            "status": complaint.status,
            "created_at": complaint.created_at,
            "message": "Complaint submitted successfully. Save your tracking secret to check status."
        }

    @staticmethod
    def get_by_ticket_and_secret(db: Session, ticket_id: str, secret: str) -> Optional[Complaint]:
        """
        Tracks a complaint using BOTH ticket ID and secret code.
        Verifies SHA-256 hash.
        """
        incoming_hash = hashlib.sha256(secret.strip().encode("utf-8")).hexdigest()
        complaint = db.query(Complaint).filter(
            Complaint.ticket_id == ticket_id.strip().upper(),
            Complaint.secret_hash == incoming_hash
        ).first()
        return complaint

    @staticmethod
    def get_by_ticket(db: Session, ticket_id: str) -> Optional[Complaint]:
        return db.query(Complaint).filter(Complaint.ticket_id == ticket_id.strip().upper()).first()

    @staticmethod
    def get_user_complaints(db: Session, user_id: str, limit: int = 50, offset: int = 0) -> List[Complaint]:
        """Returns complaints owned by the specific logged-in user."""
        return db.query(Complaint).filter(
            Complaint.user_id == str(user_id)
        ).order_by(desc(Complaint.created_at)).offset(offset).limit(limit).all()

    @staticmethod
    def get_all_admin(db: Session, status: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Complaint]:
        """Admin listing of all complaints."""
        q = db.query(Complaint)
        if status:
            try:
                q = q.filter(Complaint.status == ComplaintStatus(status.upper()))
            except ValueError:
                pass
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

    @staticmethod
    def get_all_public(db: Session, limit: int = 10) -> list:
        """
        Public feed: returns recent complaints with identity stripped.
        No name, contact, user_id, or secret_hash is exposed.
        Description is truncated to 200 chars.
        """
        complaints = db.query(Complaint).order_by(
            desc(Complaint.created_at)
        ).limit(limit).all()
        result = []
        for c in complaints:
            result.append({
                "ticket_id":   c.ticket_id,
                "category":    c.category,
                "description": (c.description or "")[:200],
                "location":    c.location,
                "status":      c.status.value if hasattr(c.status, "value") else str(c.status),
                "created_at":  c.created_at.isoformat() if c.created_at else None,
                "updated_at":  c.updated_at.isoformat() if c.updated_at else None,
                "admin_notes": c.admin_notes,
            })
        return result

    @staticmethod
    def format_for_viewer(complaint: Complaint, viewer_user: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Formats complaint ensuring anonymity & pseudonymity rules."""
        is_admin = viewer_user and (viewer_user.get("role") or "").lower() == "admin"
        viewer_id = viewer_user.get("sub") if viewer_user else None
        is_owner = viewer_id and str(viewer_id) == str(complaint.user_id)

        display_name = None
        if complaint.is_identity_hidden:
            display_name = complaint.pseudonym or "Anonymous Citizen"
        else:
            if complaint.contact_info and complaint.contact_info.name:
                display_name = complaint.contact_info.name
            elif is_owner and viewer_user.get("email"):
                display_name = viewer_user.get("email")
            else:
                display_name = "Anonymous Citizen"

        return {
            "id": complaint.id,
            "ticket_id": complaint.ticket_id,
            "category": complaint.category,
            "description": complaint.description,
            "location": complaint.location,
            "name": display_name,
            "status": complaint.status,
            "created_at": complaint.created_at,
            "updated_at": complaint.updated_at,
            "admin_notes": complaint.admin_notes,
            "image_url": complaint.image_url
        }
