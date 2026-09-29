from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.schemas.auth import UserRegister, UserLogin, UserResponse, Token
from backend.app.services.auth_service import AuthService
from backend.app.models.user import UserRole

router = APIRouter(prefix="/auth", tags=["Authentication"])

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
