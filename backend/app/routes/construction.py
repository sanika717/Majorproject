from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.services.construction_service import ConstructionService

router = APIRouter(prefix="/construction", tags=["Construction"])

@router.get("/overview")
def get_construction_overview(db: Session = Depends(get_db)):
    """
    Returns verified construction overview totals:
    Total work orders (4,729), investment (₹3,169.06 Cr), net expenditure, deductions,
    unique contractors (1,603), and ward counts.
    """
    return ConstructionService.get_overview(db)

@router.get("/clustering")
def get_construction_clustering(db: Session = Depends(get_db)):
    """
    Returns verified K-Means++ clustering results across tested K=2-8,
    with silhouette scores and detailed stats for High vs Low expenditure clusters.
    """
    return ConstructionService.get_clustering(db)

@router.get("/top-wards")
def get_top_wards(
    by: str = Query("investment", pattern="^(investment|work_orders)$"),
    limit: int = Query(15, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Returns top BBMP wards ranked by verified total investment or work orders.
    """
    if by == "work_orders":
        return ConstructionService.get_top_wards_by_work_orders(db, limit=limit)
    return ConstructionService.get_top_wards_by_investment(db, limit=limit)

@router.get("/category-tags")
def get_category_tags(db: Session = Depends(get_db)):
    """
    Returns keyword match frequency for work-order categories
    (drain, road, maintenance, development, water).
    """
    return ConstructionService.get_category_tags(db)

@router.get("/wards")
def get_ward_level_data(db: Session = Depends(get_db)):
    """
    Returns all 209 ward code summary entries (including official wards and non-standard codes).
    """
    return ConstructionService.get_ward_level_data(db)

@router.get("/full-data")
def get_full_construction_data(db: Session = Depends(get_db)):
    """
    Returns complete structured construction dataset (matching URBANPULSE_CONSTRUCTION_DATA format)
    for frontend analytics hydration.
    """
    return ConstructionService.get_full_construction_data(db)
