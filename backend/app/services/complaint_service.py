import base64
import hashlib
import io
import os
import secrets
import string
import csv
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from PIL import Image
from sqlalchemy.orm import Session
from sqlalchemy import desc, asc, or_, and_, not_, func, case

from backend.app.models.complaint import Complaint, ComplaintContact, ComplaintStatus, ComplaintPriority, ComplaintEvent
from backend.app.schemas.complaint import ComplaintSubmit, ComplaintStatusUpdate, ComplaintAdminUpdate

SLA_HOURS: Dict[str, int] = {
    "CRITICAL": 24,
    "HIGH": 72,
    "MEDIUM": 168,
    "LOW": 336
}

def compute_sla_status(
    priority: Optional[str],
    status: Any,
    created_at: Optional[datetime],
    ref_time: Optional[datetime] = None
) -> tuple[bool, Optional[float]]:
    """
    SLA (hours): CRITICAL 24, HIGH 72, MEDIUM 168, LOW 336.
    Overdue = status not in (RESOLVED, REJECTED) and now > created_at + SLA hours for the current priority.
    Returns (is_overdue: bool, hours_overdue: Optional[float]).
    """
    if not created_at:
        return False, 0.0

    st = status.value if hasattr(status, "value") else str(status or "")
    if st in ("RESOLVED", "REJECTED"):
        return False, 0.0

    pri = (priority or "MEDIUM").upper()
    sla_h = SLA_HOURS.get(pri, 168)

    now = ref_time or datetime.utcnow()
    # Normalize created_at naive/aware
    if created_at.tzinfo is not None and now.tzinfo is None:
        created_naive = created_at.astimezone(timezone.utc).replace(tzinfo=None)
    elif created_at.tzinfo is None and now.tzinfo is not None:
        created_naive = created_at
        now = now.astimezone(timezone.utc).replace(tzinfo=None)
    else:
        created_naive = created_at

    deadline = created_naive + timedelta(hours=sla_h)
    if now > deadline:
        diff_hours = round((now - deadline).total_seconds() / 3600.0, 1)
        return True, max(0.0, diff_hours)
    return False, 0.0

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

        # Write initial event
        init_event = ComplaintEvent(
            complaint_id=complaint.id,
            actor=None,
            from_status=ComplaintStatus.SUBMITTED.value,
            to_status=ComplaintStatus.SUBMITTED.value,
            note="Complaint submitted",
            created_at=complaint.created_at
        )
        db.add(init_event)

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
        overdue: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Complaint]:
        """Authority/Admin listing of all complaints with comprehensive filtering and default sort by priority_score then age."""
        q = db.query(Complaint)
        if status:
            try:
                status_enum = ComplaintStatus(status.upper().strip())
                q = q.filter(Complaint.status == status_enum)
            except ValueError:
                pass
        if priority:
            clean_pri = priority.upper().strip()
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
        if overdue is not None:
            now = datetime.utcnow()
            overdue_cond = and_(
                Complaint.status.notin_([ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED]),
                or_(*(and_(Complaint.priority == p, Complaint.created_at < now - timedelta(hours=h)) for p, h in SLA_HOURS.items()))
            )
            if overdue:
                q = q.filter(overdue_cond)
            else:
                q = q.filter(not_(overdue_cond))

        # Default sort by priority_score then age (oldest first)
        return q.order_by(desc(Complaint.priority_score), Complaint.created_at.asc()).offset(offset).limit(limit).all()

    @staticmethod
    def update_status(
        db: Session,
        ticket_id: str,
        update: ComplaintStatusUpdate,
        actor: Optional[str] = None
    ) -> Optional[Complaint]:
        complaint = ComplaintService.get_by_ticket(db, ticket_id)
        if not complaint:
            return None
        old_status = complaint.status
        status_changed = (update.status != old_status)
        complaint.status = update.status
        if update.admin_notes is not None:
            complaint.admin_notes = update.admin_notes
        complaint.updated_at = datetime.utcnow()

        if status_changed:
            if update.status == ComplaintStatus.RESOLVED:
                complaint.resolved_at = datetime.utcnow()
            elif old_status == ComplaintStatus.RESOLVED:
                complaint.resolved_at = None
            db.add(ComplaintEvent(
                complaint_id=complaint.id,
                actor=actor,
                from_status=old_status.value if hasattr(old_status, "value") else str(old_status),
                to_status=update.status.value if hasattr(update.status, "value") else str(update.status),
                note=update.admin_notes,
                created_at=datetime.utcnow()
            ))

        db.commit()
        db.refresh(complaint)
        return complaint

    @staticmethod
    def admin_review_complaint(
        db: Session,
        ticket_id: str,
        update: ComplaintAdminUpdate,
        actor: Optional[str] = None
    ) -> Optional[Complaint]:
        """
        Complete authority review action:
        - updates status (sets/clears resolved_at, writes event)
        - assigns/reassigns department
        - updates severity, public safety impact, and area impact
        - recalculates or sets priority
        - adds/updates official remarks
        """
        complaint = ComplaintService.get_by_ticket(db, ticket_id)
        if not complaint:
            return None

        old_status = complaint.status
        status_changed = (update.status is not None and update.status != old_status)
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

        if status_changed:
            if update.status == ComplaintStatus.RESOLVED:
                complaint.resolved_at = datetime.utcnow()
            elif old_status == ComplaintStatus.RESOLVED:
                complaint.resolved_at = None
            db.add(ComplaintEvent(
                complaint_id=complaint.id,
                actor=actor,
                from_status=old_status.value if hasattr(old_status, "value") else str(old_status),
                to_status=update.status.value if hasattr(update.status, "value") else str(update.status),
                note=update.admin_notes,
                created_at=datetime.utcnow()
            ))

        db.commit()
        db.refresh(complaint)
        return complaint

    @staticmethod
    def get_events(db: Session, ticket_id: str) -> List[ComplaintEvent]:
        """Retrieve full event log for a complaint (Admin only)."""
        complaint = ComplaintService.get_by_ticket(db, ticket_id)
        if not complaint:
            return []
        return db.query(ComplaintEvent).filter(
            ComplaintEvent.complaint_id == complaint.id
        ).order_by(ComplaintEvent.created_at.asc()).all()

    @staticmethod
    def get_admin_dashboard(db: Session) -> Dict[str, Any]:
        """
        Computes dashboard metrics strictly using grouped SQL queries.
        Returns:
        {
          totals: {total, submitted, under_review, in_progress, resolved, rejected, overdue, critical_open},
          sla: {compliance_pct, avg_resolution_hours},
          by_priority: {LOW, MEDIUM, HIGH, CRITICAL},
          by_category: [{label, count}],
          by_department: [{label, open, resolved}],
          by_ward: top 10 [{label, count}],
          trend: last 30 days [{date, submitted, resolved}],
          most_overdue: top 10 [{ticket_id, category, ward, priority, status, hours_overdue}]
        }
        """
        now = datetime.utcnow()

        # 1. Totals
        total = db.query(func.count(Complaint.id)).scalar() or 0
        status_counts_rows = db.query(Complaint.status, func.count(Complaint.id)).group_by(Complaint.status).all()
        status_counts = {s: cnt for s, cnt in status_counts_rows}

        open_statuses = [ComplaintStatus.SUBMITTED, ComplaintStatus.UNDER_REVIEW, ComplaintStatus.IN_PROGRESS]
        critical_open = db.query(func.count(Complaint.id)).filter(
            Complaint.priority == "CRITICAL",
            Complaint.status.in_(open_statuses)
        ).scalar() or 0

        overdue_filter = and_(
            Complaint.status.notin_([ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED]),
            or_(*(and_(Complaint.priority == p, Complaint.created_at < now - timedelta(hours=h)) for p, h in SLA_HOURS.items()))
        )
        overdue_count = db.query(func.count(Complaint.id)).filter(overdue_filter).scalar() or 0

        totals = {
            "total": total,
            "submitted": status_counts.get(ComplaintStatus.SUBMITTED, 0),
            "under_review": status_counts.get(ComplaintStatus.UNDER_REVIEW, 0),
            "in_progress": status_counts.get(ComplaintStatus.IN_PROGRESS, 0),
            "resolved": status_counts.get(ComplaintStatus.RESOLVED, 0),
            "rejected": status_counts.get(ComplaintStatus.REJECTED, 0),
            "overdue": overdue_count,
            "critical_open": critical_open
        }

        # 2. SLA Compliance & Average Resolution Hours
        resolved_count = totals["resolved"]
        if resolved_count > 0:
            resolved_rows = db.query(Complaint.priority, Complaint.created_at, Complaint.resolved_at).filter(
                Complaint.status == ComplaintStatus.RESOLVED
            ).all()
            compliant_count = 0
            total_res_hours = 0.0
            valid_res_count = 0
            for pri, cat_at, res_at in resolved_rows:
                sla_h = SLA_HOURS.get((pri or "MEDIUM").upper(), 168)
                if res_at and cat_at:
                    c_at = cat_at.replace(tzinfo=None) if cat_at.tzinfo else cat_at
                    r_at = res_at.replace(tzinfo=None) if res_at.tzinfo else res_at
                    diff_h = max(0.0, (r_at - c_at).total_seconds() / 3600.0)
                    if diff_h <= sla_h:
                        compliant_count += 1
                    total_res_hours += diff_h
                    valid_res_count += 1
            compliance_pct = round((compliant_count / len(resolved_rows)) * 100.0, 1) if resolved_rows else None
            avg_res_hours = round(total_res_hours / valid_res_count, 1) if valid_res_count > 0 else None
            sla = {
                "compliance_pct": compliance_pct,
                "avg_resolution_hours": avg_res_hours
            }
        else:
            sla = {
                "compliance_pct": None,
                "avg_resolution_hours": None
            }

        # 3. By Priority
        pri_rows = db.query(Complaint.priority, func.count(Complaint.id)).group_by(Complaint.priority).all()
        by_priority = {p: 0 for p in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]}
        for p, cnt in pri_rows:
            if p and p.upper() in by_priority:
                by_priority[p.upper()] = cnt

        # 4. By Category
        cat_rows = db.query(
            Complaint.category,
            func.count(Complaint.id)
        ).group_by(Complaint.category).order_by(func.count(Complaint.id).desc()).all()
        by_category = [{"label": cat, "count": cnt} for cat, cnt in cat_rows if cat]

        # 5. By Department (open vs resolved)
        dept_rows = db.query(
            Complaint.department,
            func.sum(case((Complaint.status.in_(open_statuses), 1), else_=0)).label("open_cnt"),
            func.sum(case((Complaint.status == ComplaintStatus.RESOLVED, 1), else_=0)).label("res_cnt")
        ).filter(Complaint.department.isnot(None), Complaint.department != "").group_by(Complaint.department).all()
        by_department = [
            {"label": dept, "open": int(o or 0), "resolved": int(r or 0)}
            for dept, o, r in dept_rows if dept
        ]

        # 6. By Ward (Top 10)
        ward_rows = db.query(
            Complaint.ward,
            func.count(Complaint.id)
        ).filter(Complaint.ward.isnot(None), Complaint.ward != "").group_by(Complaint.ward).order_by(func.count(Complaint.id).desc()).limit(10).all()
        by_ward = [{"label": ward, "count": cnt} for ward, cnt in ward_rows]

        # 7. Trend (Last 30 days: submitted vs resolved)
        today = now.date()
        start_30 = today - timedelta(days=29)
        start_dt = datetime.combine(start_30, datetime.min.time())

        sub_rows = db.query(
            func.date(Complaint.created_at),
            func.count(Complaint.id)
        ).filter(Complaint.created_at >= start_dt).group_by(func.date(Complaint.created_at)).all()
        sub_map = {str(d): c for d, c in sub_rows}

        res_rows = db.query(
            func.date(Complaint.resolved_at),
            func.count(Complaint.id)
        ).filter(
            Complaint.status == ComplaintStatus.RESOLVED,
            Complaint.resolved_at.isnot(None),
            Complaint.resolved_at >= start_dt
        ).group_by(func.date(Complaint.resolved_at)).all()
        res_map = {str(d): c for d, c in res_rows}

        trend = []
        for i in range(30):
            cur_str = (start_30 + timedelta(days=i)).isoformat()
            trend.append({
                "date": cur_str,
                "submitted": sub_map.get(cur_str, 0),
                "resolved": res_map.get(cur_str, 0)
            })

        # 8. Most Overdue (Top 10)
        overdue_complaints = db.query(Complaint).filter(overdue_filter).all()
        overdue_list = []
        for c in overdue_complaints:
            is_ov, h_ov = compute_sla_status(c.priority, c.status, c.created_at, ref_time=now)
            if is_ov and h_ov is not None and h_ov > 0:
                overdue_list.append({
                    "ticket_id": c.ticket_id,
                    "category": c.category,
                    "ward": c.ward,
                    "priority": c.priority,
                    "status": c.status.value if hasattr(c.status, "value") else str(c.status),
                    "hours_overdue": h_ov
                })
        overdue_list.sort(key=lambda x: x["hours_overdue"], reverse=True)
        most_overdue = overdue_list[:10]

        return {
            "totals": totals,
            "sla": sla,
            "by_priority": by_priority,
            "by_category": by_category,
            "by_department": by_department,
            "by_ward": by_ward,
            "trend": trend,
            "most_overdue": most_overdue
        }

    @staticmethod
    def export_complaints_csv(
        db: Session,
        ticket_id: Optional[str] = None,
        category: Optional[str] = None,
        ward: Optional[str] = None,
        department: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        created_at: Optional[str] = None,
        resolved_at: Optional[str] = None,
        is_overdue: Optional[bool] = None,
        search: Optional[str] = None
    ) -> str:
        """
        Exports complaints to CSV format honoring the same filters as the admin list.
        Strict privacy: Excludes name, contact, user_id, pseudonym and secret_hash.
        """
        q = db.query(Complaint)
        if ticket_id:
            q = q.filter(Complaint.ticket_id.ilike(f"%{ticket_id.strip()}%"))
        if category:
            q = q.filter(Complaint.category.ilike(f"%{category.strip()}%"))
        if ward:
            q = q.filter(Complaint.ward.ilike(f"%{ward.strip()}%"))
        if department:
            q = q.filter(Complaint.department.ilike(f"%{department.strip()}%"))
        if priority:
            q = q.filter(Complaint.priority == priority.upper().strip())
        if status:
            try:
                status_enum = ComplaintStatus(status.upper().strip())
                q = q.filter(Complaint.status == status_enum)
            except ValueError:
                pass
        if search:
            s = f"%{search.strip()}%"
            q = q.filter(or_(
                Complaint.ticket_id.ilike(s),
                Complaint.category.ilike(s),
                Complaint.description.ilike(s),
                Complaint.location.ilike(s),
                Complaint.ward.ilike(s)
            ))
        if is_overdue is not None:
            now = datetime.utcnow()
            overdue_cond = and_(
                Complaint.status.notin_([ComplaintStatus.RESOLVED, ComplaintStatus.REJECTED]),
                or_(*(and_(Complaint.priority == p, Complaint.created_at < now - timedelta(hours=h)) for p, h in SLA_HOURS.items()))
            )
            if is_overdue:
                q = q.filter(overdue_cond)
            else:
                q = q.filter(not_(overdue_cond))

        complaints = q.order_by(desc(Complaint.priority_score), Complaint.created_at.asc()).all()

        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow([
            "ticket_id", "category", "ward", "department", "priority",
            "status", "created_at", "resolved_at", "is_overdue"
        ])

        now = datetime.utcnow()
        for c in complaints:
            c_overdue, _ = compute_sla_status(c.priority, c.status, c.created_at, ref_time=now)
            st_val = c.status.value if hasattr(c.status, "value") else str(c.status)
            c_at = c.created_at.isoformat() if c.created_at else ""
            r_at = c.resolved_at.isoformat() if c.resolved_at else ""
            writer.writerow([
                c.ticket_id,
                c.category or "",
                c.ward or "",
                c.department or "",
                c.priority or "",
                st_val,
                c_at,
                r_at,
                "true" if c_overdue else "false"
            ])

        return output.getvalue()

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
        cat_rows = db.query(Complaint.category, func.count(Complaint.id)).group_by(Complaint.category).all()
        for cat, cnt in cat_rows:
            if cat:
                by_category[cat] = cnt

        by_department = {}
        dept_rows = db.query(Complaint.department, func.count(Complaint.id)).filter(Complaint.department.isnot(None)).group_by(Complaint.department).all()
        for dept, cnt in dept_rows:
            if dept:
                by_department[dept] = cnt

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
                "resolved_at":          c.resolved_at.isoformat() if c.resolved_at else None,
                "admin_notes":          c.admin_notes,
            })
        return result

    @staticmethod
    def format_for_viewer(
        complaint: Complaint,
        viewer_user: Optional[Dict[str, Any]] = None,
        include_timeline: bool = False
    ) -> Dict[str, Any]:
        """
        Formats complaint ensuring anonymity & pseudonymity rules.
        Complainant contact info is NEVER exposed.
        Computes SLA overdue state dynamically.
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

        is_overdue, hours_overdue = compute_sla_status(
            complaint.priority,
            complaint.status,
            complaint.created_at
        )

        timeline_items = None
        if include_timeline and hasattr(complaint, "events") and complaint.events:
            timeline_items = [
                {"status": e.to_status, "at": e.created_at}
                for e in complaint.events
            ]

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
            "resolved_at":          complaint.resolved_at,
            "is_overdue":           is_overdue,
            "hours_overdue":        hours_overdue,
            "admin_notes":          complaint.admin_notes,
            "image_url":            complaint.image_url,
            "timeline":             timeline_items
        }

