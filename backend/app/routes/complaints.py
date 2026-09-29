from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.complaint import ComplaintSubmit, ComplaintResponse, ComplaintStatusUpdate
from backend.app.services.complaint_service import ComplaintService

router = APIRouter(prefix="/complaints", tags=["Complaints"])

@router.post("/", response_model=ComplaintResponse, status_code=status.HTTP_201_CREATED)
def submit_complaint(data: ComplaintSubmit, db: Session = Depends(get_db)):
    """
    Submit a public complaint about a civic issue in Bengaluru.
    Returns a unique ticket ID for tracking.
    """
    return ComplaintService.submit_complaint(db, data)

@router.get("/", response_model=List[ComplaintResponse])
def list_complaints(
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status: SUBMITTED, UNDER_REVIEW, IN_PROGRESS, RESOLVED, REJECTED"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    List all public complaints. Optionally filter by status.
    """
    return ComplaintService.get_all(db, status=status_filter, limit=limit, offset=offset)

@router.get("/stats")
def get_complaint_stats(db: Session = Depends(get_db)):
    """
    Returns complaint submission statistics grouped by status and category.
    """
    return ComplaintService.get_stats(db)

@router.get("/{ticket_id}", response_model=ComplaintResponse)
def get_complaint(ticket_id: str, db: Session = Depends(get_db)):
    """
    Retrieve a specific complaint by its ticket ID (e.g. UP-2026-AB12CD).
    """
    complaint = ComplaintService.get_by_ticket(db, ticket_id)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Complaint with ticket ID '{ticket_id}' not found.")
    return complaint

@router.patch("/{ticket_id}/status", response_model=ComplaintResponse)
def update_complaint_status(ticket_id: str, update: ComplaintStatusUpdate, db: Session = Depends(get_db)):
    """
    Update the status of a complaint (admin action). Accepts admin notes.
    """
    complaint = ComplaintService.update_status(db, ticket_id, update)
    if not complaint:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Complaint '{ticket_id}' not found.")
    return complaint
