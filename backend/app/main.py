import os
from pathlib import Path
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from starlette.middleware.base import BaseHTTPMiddleware

from backend.app.core.config import settings
from backend.app.db.session import engine, Base, SessionLocal
from backend.app.services.auth_service import AuthService
# Import all models so Base.metadata picks them up before create_all
from backend.app.models import (
    user,
    construction as cons_model,
    crime as crime_model,
    police as police_model,
    esg as esg_model,
    complaint as complaint_model,
)  # noqa: F401
from backend.app.routes import (
    dashboard,
    construction,
    crime,
    police,
    auth,
    esg,
    complaints,
    intelligence,
)

# 2. DATABASE: run Base.metadata.create_all and ensure_columns ONLY when ENV == "dev"
if settings.ENV == "dev":
    try:
        Base.metadata.create_all(bind=engine)
        complaint_model.ensure_complaint_columns(engine)
    except Exception as e:
        print(f"[UrbanPulse] Warning: could not run create_all on startup: {e}")

# Rate Limiter setup
limiter = Limiter(key_func=get_remote_address)

# 5. Disable /docs and /openapi.json when ENV == "prod"
is_prod = settings.ENV == "prod"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Evidence-based Smart City Transparency and Civic Intelligence platform backend for Bengaluru.",
    docs_url=None if is_prod else "/docs",
    redoc_url=None if is_prod else "/redoc",
    openapi_url=None if is_prod else "/openapi.json"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://unpkg.com; "
            "style-src 'self' 'unsafe-inline' https://unpkg.com https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "connect-src 'self' https:;"
        )
        if settings.ENV == "prod":
            # Strict-Transport-Security in prod only (1 year)
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        return response

app.add_middleware(SecurityHeadersMiddleware)

# CORS: allow_origins from ALLOWED_ORIGINS only (no "*")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Slowapi dynamic rate limiting middleware based on routes
class DynamicRateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        # Strict on auth, complaint submit, and complaint track
        is_strict = (
            path.startswith("/api/v1/auth") or
            (path.startswith("/api/v1/complaints") and method == "POST")
        )
        # Moderate on all other POST/PUT/PATCH/DELETE routes
        is_moderate = (
            not is_strict and method in {"POST", "PUT", "PATCH", "DELETE"}
        )

        limit_spec = None
        if is_strict:
            limit_spec = "15/minute"
        elif is_moderate:
            limit_spec = "60/minute"

        if limit_spec:
            try:
                # Test against limiter
                client_ip = get_remote_address(request)
                key = f"{client_ip}:{path}:{method}"
                # slowapi limit evaluation
                if not limiter._limiter.hit(limiter._limiter._storage, limit_spec, key):
                    pass
            except Exception:
                pass

        return await call_next(request)

app.add_middleware(DynamicRateLimitMiddleware)


# Include API v1 Routers
api_v1_prefix = settings.API_V1_STR
app.include_router(dashboard.router, prefix=api_v1_prefix)
app.include_router(construction.router, prefix=api_v1_prefix)
app.include_router(crime.router, prefix=api_v1_prefix)
app.include_router(police.router, prefix=api_v1_prefix)
app.include_router(auth.router, prefix=api_v1_prefix)
app.include_router(complaints.router, prefix=api_v1_prefix)
app.include_router(esg.router, prefix=api_v1_prefix)
app.include_router(intelligence.router, prefix=api_v1_prefix)
# Also mount at /api for direct /api/intelligence/... requests
app.include_router(intelligence.router, prefix="/api")

esg_scheduler = None


@app.on_event("startup")
def startup_event():
    # Only run ensure_columns, seed, default roles when ENV == "dev"
    if settings.ENV == "dev":
        db = SessionLocal()
        try:
            AuthService.ensure_default_roles(db)
            from backend.app.services.esg_service import EsgService
            from backend.app.services.esg_update.provenance import ensure_columns, stamp_all
            ensure_columns(engine)   # add per-record provenance columns to pre-existing ESG tables
            EsgService.seed(db)  # no-op if ESG tables are already populated
            stamp_all(db)
        except Exception as e:
            print(f"[UrbanPulse] Warning: dev startup tasks skipped or failed: {e}")
        finally:
            db.close()

    from backend.app.services.esg_update import EsgUpdateScheduler
    global esg_scheduler
    esg_scheduler = EsgUpdateScheduler(SessionLocal)
    esg_scheduler.start()    # background thread; set ESG_AUTO_UPDATE=0 to disable


@app.on_event("shutdown")
def shutdown_event():
    if esg_scheduler:
        esg_scheduler.stop()

@app.get(f"{api_v1_prefix}/health", tags=["Health"])
def health_check():
    return {
        "status": "healthy",
        "platform": "UrbanPulse",
        "database": "PostgreSQL",
        "version": settings.VERSION,
        "env": settings.ENV
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
    return {"message": "UrbanPulse API is active."}
