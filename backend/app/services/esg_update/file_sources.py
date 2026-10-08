"""Carbon + water: no public machine-readable feed exists for these datasets (BBMP BCAP is a PDF report;
KSPCB lake data is a one-off CSV on karnataka.data.gov.in). So the job (1) reloads the dataset into the DB
whenever the verified JSON in frontend/data/esg/ changes, and (2) checks that the official source is still
reachable. It never edits values itself."""
from typing import Any, Dict
from sqlalchemy.orm import Session
from backend.app.models.esg import EsgUpdateRun
from backend.app.services.esg_update.http import fetch, UpdateError
from backend.app.services.esg_update.provenance import file_hash

DATASETS = {
    "carbon": (["carbon_emissions.json"], "https://apps.bbmpgov.in/bcap/PDF/Executive%20summary_English%2018072025.pdf"),
    "water": (["water_quality_lakes_2020_21.json"], "https://karnataka.data.gov.in/resource/water-quality-lakestanks-bangalore-during-2020-2021"),
}


def run(db: Session, job: str) -> Dict[str, Any]:
    from backend.app.services.esg_service import EsgService
    files, url = DATASETS[job]
    h = file_hash(files)
    prev = (db.query(EsgUpdateRun).filter(EsgUpdateRun.job == job, EsgUpdateRun.status == "ok", EsgUpdateRun.data_hash.isnot(None))
            .order_by(EsgUpdateRun.id.desc()).first())
    try:
        fetch(url, timeout=15, method="HEAD")
        reach = "official source reachable"
    except UpdateError as e:
        reach = f"official source not verifiable right now ({e})"
    if prev and prev.data_hash == h:
        return {"status": "ok", "unchanged": 1, "data_hash": h, "source_url": url,
                "message": f"verified file unchanged; {reach}"}
    EsgService.reseed_dataset(db, job)
    return {"status": "ok", "updated": 1, "data_hash": h, "source_url": url,
            "message": f"verified file {'first loaded' if not prev else 'changed'} -> dataset reloaded; {reach}"}
