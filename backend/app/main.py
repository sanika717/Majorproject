import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from backend.app.core.config import settings
from backend.app.db.session import engine, Base, SessionLocal
from backend.app.services.auth_service import AuthService
# Import all models so Base.metadata picks them up before create_all
from backend.app.models import user, construction as cons_model, crime as crime_model, police as police_model  # noqa: F401
from backend.app.models.complaint import Complaint  # noqa: F401
from backend.app.routes import (
    dashboard,
    construction,
    crime,
    police,
    auth,
)
from backend.app.routes import complaints

# Create all database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Evidence-based Smart City Transparency and Civic Intelligence platform backend for Bengaluru."
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all for flexible local dev / browser requests
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API v1 Routers
api_v1_prefix = settings.API_V1_STR
app.include_router(dashboard.router, prefix=api_v1_prefix)
app.include_router(construction.router, prefix=api_v1_prefix)
app.include_router(crime.router, prefix=api_v1_prefix)
app.include_router(police.router, prefix=api_v1_prefix)
app.include_router(auth.router, prefix=api_v1_prefix)
app.include_router(complaints.router, prefix=api_v1_prefix)

@app.on_event("startup")
def startup_event():
    # Ensure default roles & seed baseline if needed
    db = SessionLocal()
    try:
        AuthService.ensure_default_roles(db)
    finally:
        db.close()

@app.get(f"{api_v1_prefix}/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "platform": "UrbanPulse",
        "database": "PostgreSQL",
        "version": settings.VERSION
    }

# Mount static frontend directory if present
BASE_DIR = Path(__file__).resolve().parent.parent.parent
frontend_dir = BASE_DIR / "frontend"
if frontend_dir.exists():
    app.mount("/frontend", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")

@app.get("/", include_in_schema=False)
def root_redirect():
    if frontend_dir.exists():
        return RedirectResponse(url="/frontend/dashboard.html")
    return {"message": "UrbanPulse API is active. Visit /docs for OpenAPI documentation."}
