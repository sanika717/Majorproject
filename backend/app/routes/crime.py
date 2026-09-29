from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.services.crime_service import CrimeService

router = APIRouter(prefix="/crime", tags=["Crime"])

@router.get("/historical")
def get_crime_historical(db: Session = Depends(get_db)):
    """
    Returns verified D47 historical statistics for Bengaluru City (2014-2021 Up to Dec):
    Total crimes (35,971), Fatal (5,437), Non-fatal (30,534), Fatal % (15.11%),
    and peak risk score (71.70, High Risk 2016).
    """
    return CrimeService.get_historical(db)

@router.get("/risk-formula")
def get_risk_formula(db: Session = Depends(get_db)):
    """
    Returns the UrbanPulse City Crime Risk Score formula specifications.
    """
    return CrimeService.get_risk_formula(db)

@router.get("/analytics")
def get_crime_analytics(
    category: str = Query("all", description="Category: all, women, children, cyber, suicides, accidental"),
    year: str = Query("2023", description="Year: 2021, 2022, 2023 (for category tabs)"),
    db: Session = Depends(get_db)
):
    """
    Dynamically returns verified crime metrics, KPIs, breakdown items, and charts
    for the selected category and year.
    """
    return CrimeService.get_crime_analytics(db, category=category, year=year)

@router.get("/full-data")
def get_full_crime_data(db: Session = Depends(get_db)):
    """
    Returns the complete verified crime dataset matching URBANPULSE_DATA format.
    """
    return CrimeService.get_full_crime_data(db)

@router.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    """
    Returns category metadata and available years.
    """
    data = CrimeService.get_full_crime_data(db)
    return {
        "historical": data["historical"],
        "categories": list(data.get("categories", {}).keys()),
        "verified_years": ["2021", "2022", "2023"]
    }
