from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.routes.esg import router as esg_router

app = FastAPI(
    title="UrbanPulse ESG",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(esg_router, prefix="/api/v1")

frontend_dir = Path(__file__).resolve().parents[2] / "frontend"

app.mount(
    "/",
    StaticFiles(directory=str(frontend_dir), html=True),
    name="frontend",
)

@app.get("/api/v1/health")
def health():
    return {
        "status": "healthy",
        "service": "UrbanPulse ESG"
    }
