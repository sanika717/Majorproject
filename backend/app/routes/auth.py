from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.schemas.auth import UserRegister, UserLogin, UserResponse, Token
from backend.app.services.auth_service import (
    AuthService,
    get_current_user,
    get_current_user_optional,
    require_role
)
from backend.app.models.user import UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])

@router.get("/config")
def get_auth_config():
    """
    Returns public Supabase configuration for the frontend client.
    Never exposes backend secrets or JWT secrets.
    """
    return {
        "supabase_url": settings.SUPABASE_URL,
        "supabase_anon_key": settings.SUPABASE_ANON_KEY,
        "env": settings.ENV
    }

@router.get("/me")
def get_current_user_profile(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Returns verified user identity, role, and metadata decoded from Supabase JWT.
    """
    return {
        "status": "authenticated",
        "user": current_user
    }

@router.get("/admin-check")
def verify_admin_access(
    admin_user: Dict[str, Any] = Depends(require_role("admin"))
):
    """
    Strict server-side verification for Administrator privileges.
    Guarantees that access is restricted to verified administrators.
    Never trusts client-provided login parameters.
    """
    return {
        "status": "authorized",
        "is_admin": True,
        "role": "admin",
        "user": {
            "id": admin_user.get("id"),
            "email": admin_user.get("email"),
            "role": admin_user.get("role")
        }
    }

@router.post("/sync")
def sync_supabase_user(
    db: Session = Depends(get_db),
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """
    Synchronizes the authenticated Supabase user into the local PostgreSQL database.
    """
    db_user = AuthService.sync_supabase_user(db, current_user)
    return {
        "status": "synced",
        "user": {
            "id": db_user.id,
            "username": db_user.username,
            "email": db_user.email,
            "role": db_user.role.value,
            "is_active": db_user.is_active
        }
    }

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: UserRegister, db: Session = Depends(get_db)):
    """
    Register a new user account (defaults to USER role, can be ADMIN if designated).
    """
    try:
        user = AuthService.register_user(db, user_in)
        return user
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/login", response_model=Token)
def login(creds: UserLogin, db: Session = Depends(get_db)):
    """
    Authenticate a user or admin and return access token + user details.
    """
    user = AuthService.authenticate_user(db, creds)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials. Please check your username/email and password."
        )
    token = AuthService.create_token(user)
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user
    }

@router.get("/roles")
def get_supported_roles():
    """
    Returns available authentication roles (USER and ADMIN).
    """
    return {
        "roles": [r.value for r in UserRole],
        "default": UserRole.USER.value
    }

