from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request, Response
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.complaint import (
    ComplaintSubmit,
    ComplaintSubmitResponse,
    ComplaintResponse,
    ComplaintTrackRequest,
    ComplaintStatusUpdate,
    ComplaintAdminUpdate,
    ComplaintEventResponse
)
from backend.app.services.complaint_service import ComplaintService
from backend.app.services.auth_service import (
    get_current_user,
    get_current_user_optional,
    require_role
)

router = APIRouter(prefix="/complaints", tags=["Complaints"])

@router.post("/", response_model=ComplaintSubmitResponse, status_code=status.HTTP_201_CREATED)
def submit_complaint(
    data: ComplaintSubmit,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Submit a complaint (Anonymous or Logged In).
    Name and contact are optional and stored separately for privacy.
    Generates a tracking ID and a secret code (token_urlsafe(24)).
    Returns the secret ONCE in this response.
    """
    return ComplaintService.submit_complaint(db, data, current_user=current_user)

@router.post("/track", response_model=ComplaintResponse)
def track_complaint(
    payload: ComplaintTrackRequest,
    db: Session = Depends(get_db),
    current_user: Optional[Dict[str, Any]] = Depends(get_current_user_optional)
):
    """
    Tracking a complaint requires BOTH tracking ID and secret code.
    Verifies SHA-256 hash. SQL-safe parameterized query.
    Never reveals complainant contact details.
    Includes optional lifecycle status timeline.
    """
    complaint = ComplaintService.get_by_ticket_and_secret(db, payload.ticket_id, payload.secret)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or invalid tracking secret."
        )
    return ComplaintService.format_for_viewer(complaint, viewer_user=current_user, include_timeline=True)

@router.get("/my", response_model=List[ComplaintResponse])
def get_my_complaints(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Users can only read their own complaints (ownership check).
    """
    user_id = current_user.get("sub") or current_user.get("id")
    complaints = ComplaintService.get_user_complaints(db, user_id, limit=limit, offset=offset)
    return [ComplaintService.format_for_viewer(c, viewer_user=current_user) for c in complaints]

@router.get("/admin/dashboard", dependencies=[Depends(require_role("admin"))])
def get_admin_dashboard(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Admin Dashboard metrics:
    Grouped SQL aggregations of totals, SLA compliance %, resolution times, priority counts,
    category distribution, department open/resolved, top-10 wards, 30-day trends, and most overdue list.
    """
    return ComplaintService.get_admin_dashboard(db)

@router.get("/admin/export.csv", dependencies=[Depends(require_role("admin"))])
def export_complaints_csv(
    ticket_id: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    ward: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    created_at: Optional[str] = Query(None),
    resolved_at: Optional[str] = Query(None),
    is_overdue: Optional[bool] = Query(None, alias="is_overdue"),
    search: Optional[str] = Query(None, alias="search"),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Export complaints to CSV (Admin only).
    Honors identical filters to the admin complaints list.
    Excludes name, contact, email, and any citizen identity fields.
    """
    csv_data = ComplaintService.export_complaints_csv(
        db,
        ticket_id=ticket_id,
        category=category,
        ward=ward,
        department=department,
        priority=priority,
        status=status_filter,
        created_at=created_at,
        resolved_at=resolved_at,
        is_overdue=is_overdue,
        search=search
    )
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=complaints_export.csv"}
    )

@router.get("/", response_model=List[ComplaintResponse], dependencies=[Depends(require_role("admin"))])
def list_all_complaints_admin(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    department_filter: Optional[str] = Query(None, alias="department"),
    search: Optional[str] = Query(None, alias="search"),
    overdue_filter: Optional[bool] = Query(None, alias="overdue"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all complaints (Admin/Authority only).
    Supports filtering by status, priority, department, search term, and overdue status.
    Default sorted by priority_score desc then age (oldest first).
    """
    complaints = ComplaintService.get_all_admin(
        db,
        status=status_filter,
        priority=priority_filter,
        department=department_filter,
        search=search,
        overdue=overdue_filter,
        limit=limit,
        offset=offset
    )
    return [ComplaintService.format_for_viewer(c, viewer_user=current_user) for c in complaints]

@router.get("/stats")
def get_complaint_stats(db: Session = Depends(get_db)):
    """
    Returns aggregated complaint submission statistics strictly from PostgreSQL.
    Public read-only.
    """
    return ComplaintService.get_stats(db)

@router.get("/public", response_model=List[dict])
def list_public_complaints(
    limit: int = Query(15, ge=1, le=50),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Returns the most recent complaints for the public feed.
    No auth required. Complainant identity and contact fields are strictly stripped.
    Description is truncated to 200 chars.
    """
    complaints = ComplaintService.get_all_public(db, limit=limit, offset=offset)
    return complaints

@router.get("/{ticket_id}", response_model=ComplaintResponse)
def get_complaint(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve a specific complaint by ticket ID with ownership / admin check.
    """
    complaint = ComplaintService.get_by_ticket(db, ticket_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with ticket ID '{ticket_id}' not found."
        )

    is_admin = (current_user.get("role") or "").lower() == "admin"
    user_id = str(current_user.get("sub") or current_user.get("id"))
    is_owner = str(complaint.user_id) == user_id

    if not is_admin and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: you can only view your own complaints or track with a secret."
        )

    return ComplaintService.format_for_viewer(complaint, viewer_user=current_user, include_timeline=True)

@router.get("/{ticket_id}/events", response_model=List[ComplaintEventResponse], dependencies=[Depends(require_role("admin"))])
def get_complaint_events(
    ticket_id: str,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Retrieve audit lifecycle events for a specific complaint (Admin only).
    """
    complaint = ComplaintService.get_by_ticket(db, ticket_id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with ticket ID '{ticket_id}' not found."
        )
    return ComplaintService.get_events(db, ticket_id)

@router.patch("/{ticket_id}/admin-review", response_model=ComplaintResponse, dependencies=[Depends(require_role("admin"))])
def review_complaint_admin(
    ticket_id: str,
    review: ComplaintAdminUpdate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Authority/Admin review action:
    - Assign/reassign municipal department
    - Update complaint status
    - Adjust severity, public safety impact, and affected-area impact
    - Set or recalculate priority
    - Add administrative remarks/updates
    - Records ComplaintEvent with admin actor
    """
    actor = current_user.get("email") or current_user.get("username")
    complaint = ComplaintService.admin_review_complaint(db, ticket_id, review, actor=actor)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{ticket_id}' not found."
        )
    return ComplaintService.format_for_viewer(complaint, viewer_user=current_user)

@router.patch("/{ticket_id}/status", response_model=ComplaintResponse, dependencies=[Depends(require_role("admin"))])
def update_complaint_status(
    ticket_id: str,
    update: ComplaintStatusUpdate,
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Legacy/simple status update and admin notes (Admin only).
    Records ComplaintEvent with admin actor.
    """
    actor = current_user.get("email") or current_user.get("username")
    complaint = ComplaintService.update_status(db, ticket_id, update, actor=actor)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{ticket_id}' not found."
        )
    return ComplaintService.format_for_viewer(complaint, viewer_user=current_user)

