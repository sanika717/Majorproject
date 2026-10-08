"""Reload ESG tables from frontend/data/esg/*.json. Run from project root: python3 -m backend.scripts.seed_esg"""
from backend.app.db.session import engine, Base, SessionLocal
from backend.app.models import esg  # noqa: F401
from backend.app.services.esg_service import EsgService

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        print("ESG data reseeded:", EsgService.seed(db, force=True))
    finally:
        db.close()
