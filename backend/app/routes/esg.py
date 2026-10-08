from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.db.session import SessionLocal
from backend.app.services.esg_service import EsgService
from backend.app.services.esg_update import run_job, JOBS
from backend.app.services.auth_service import require_role

router = APIRouter(prefix="/esg", tags=["ESG"])


@router.get("/air-quality")
def get_air_quality(db: Session = Depends(get_db)):
    """Area-wise (station-wise) ambient air pollutant data with source and year."""
    return EsgService.air_quality(db)


@router.get("/carbon-emissions")
def get_carbon_emissions(db: Session = Depends(get_db)):
    """Bengaluru GHG emissions by year/sector (only years with an official inventory)."""
    return EsgService.carbon(db)


@router.get("/water-quality")
def get_water_quality(db: Session = Depends(get_db)):
    """KSPCB lake/tank water-quality summary for Bangalore Urban."""
    return EsgService.water(db)


@router.get("/electricity")
def get_electricity(db: Session = Depends(get_db)):
    """Electricity consumption by area/year; empty with a reason when no genuine data is imported."""
    return EsgService.electricity(db)


@router.post("/reseed", dependencies=[Depends(require_role("admin"))])
def reseed(db: Session = Depends(get_db)):
    """Reload ESG tables from frontend/data/esg/*.json (Admin only)."""
    result = {"reseeded": EsgService.seed(db, force=True)}
    run_job("electricity", SessionLocal, force=True)   # reseed clears auto-fetched rows; fetch them again
    return result


@router.get("/update-status")
def update_status(db: Session = Depends(get_db)):
    """Last run of each auto-update job + current ESG data version (changes => scores recalculated)."""
    return EsgService.update_status(db)


@router.post("/update-now", dependencies=[Depends(require_role("admin"))])
def update_now(job: str = "all"):
    """Run one auto-update job (air|electricity|carbon|water) or all of them immediately (Admin only)."""
    if job != "all" and job not in JOBS:
        raise HTTPException(400, f"job must be one of {list(JOBS)} or 'all'")
    return [run_job(j, SessionLocal, force=True) for j in (JOBS if job == "all" else [job])]
