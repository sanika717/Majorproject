from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.schemas.complaint import (
    ComplaintSubmit,
    ComplaintSubmitResponse,
    ComplaintResponse,
    ComplaintTrackRequest,
    ComplaintStatusUpdate,
    ComplaintAdminUpdate
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
    """
    complaint = ComplaintService.get_by_ticket_and_secret(db, payload.ticket_id, payload.secret)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complaint not found or invalid tracking secret."
        )
    return ComplaintService.format_for_viewer(complaint, viewer_user=current_user)

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

@router.get("/", response_model=List[ComplaintResponse], dependencies=[Depends(require_role("admin"))])
def list_all_complaints_admin(
    status_filter: Optional[str] = Query(None, alias="status"),
    priority_filter: Optional[str] = Query(None, alias="priority"),
    department_filter: Optional[str] = Query(None, alias="department"),
    search: Optional[str] = Query(None, alias="search"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    List all complaints (Admin/Authority only).
    Supports filtering by status, priority, department, and search term.
    Admins see pseudonyms for users who chose to hide their identity.
    """
    complaints = ComplaintService.get_all_admin(
        db,
        status=status_filter,
        priority=priority_filter,
        department=department_filter,
        search=search,
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

    return ComplaintService.format_for_viewer(complaint, viewer_user=current_user)

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
    """
    complaint = ComplaintService.admin_review_complaint(db, ticket_id, review)
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
    """
    complaint = ComplaintService.update_status(db, ticket_id, update)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint '{ticket_id}' not found."
        )
    return ComplaintService.format_for_viewer(complaint, viewer_user=current_user)
