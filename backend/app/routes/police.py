from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.services.police_service import PoliceService

router = APIRouter(prefix="/police", tags=["Police"])

@router.get("/locations")
def get_police_locations(
    category: Optional[str] = Query(None, description="Filter by category e.g. 'Police Station', 'Police Outpost', 'Railway Police Station'"),
    db: Session = Depends(get_db)
):
    """
    Returns the 150 verified mapped police locations extracted from official KML files.
    """
    return PoliceService.get_all_locations(db, category=category)

@router.get("/summary")
def get_police_summary(db: Session = Depends(get_db)):
    """
    Returns verified location counts grouped by type (Police Station, Outpost, Railway Police Station).
    """
    return PoliceService.get_summary(db)
