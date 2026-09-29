from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.services.dashboard_service import DashboardService

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/kpis")
def get_dashboard_kpis(db: Session = Depends(get_db)):
    """
    Returns headline verified metrics for the Dashboard map-first page:
    - BBMP construction work orders & investment sum
    - D47 Recorded crimes & period
    - Verified police locations count
    """
    return DashboardService.get_headline_kpis(db)
