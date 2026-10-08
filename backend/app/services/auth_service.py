import hashlib
import hmac
import secrets
import time
from typing import Optional, Dict, Any
import requests
import jwt
from jwt import PyJWKClient
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from backend.app.core.config import settings
from backend.app.db.session import get_db
from backend.app.models.user import User, UserRole
from backend.app.schemas.auth import UserRegister, UserLogin

# Security scheme for Bearer token in Swagger/FastAPI
security_bearer = HTTPBearer(auto_error=False)

# Cache for JWKS client if SUPABASE_URL is provided
_jwks_client: Optional[PyJWKClient] = None

def _get_jwks_client() -> Optional[PyJWKClient]:
    global _jwks_client
    if _jwks_client is not None:
        return _jwks_client
    if settings.SUPABASE_URL:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        try:
            _jwks_client = PyJWKClient(jwks_url)
            return _jwks_client
        except Exception:
            return None
    return None

def decode_supabase_jwt(token: str) -> Dict[str, Any]:
    """
    Verifies and decodes a Supabase JWT.
    Supports SUPABASE_JWT_SECRET (symmetric HS256) and JWKS (asymmetric RS256/ES256).
    """
    unverified_header = jwt.get_unverified_header(token)
    alg = unverified_header.get("alg", "HS256")

    # If asymmetric algorithm and SUPABASE_URL configured, try JWKS
    if alg in ["RS256", "ES256"] or not settings.SUPABASE_JWT_SECRET:
        jwks = _get_jwks_client()
        if jwks:
            try:
                signing_key = jwks.get_signing_key_from_jwt(token)
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[alg],
                    options={"verify_aud": False}
                )
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=f"Invalid JWT via JWKS: {str(e)}"
                )

    # Use SUPABASE_JWT_SECRET
    if settings.SUPABASE_JWT_SECRET:
        try:
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid or expired token: {str(e)}"
            )

    # If neither secret nor JWKS configured, fallback:
    # In dev mode, allow inspection or raise clear configuration error
    if settings.ENV == "dev":
        # Attempt unverified decode in dev if no secret configured
        try:
            return jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not parse token: {str(e)}"
            )

    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Authentication secret is not configured on the server."
    )

def get_current_user_optional(
    auth_creds: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Optional[Dict[str, Any]]:
    """Optional user dependency for routes accessible both anonymously and authenticated."""
    if not auth_creds or not auth_creds.credentials:
        return None
    token = auth_creds.credentials
    payload = decode_supabase_jwt(token)
    
    app_meta = payload.get("app_metadata") or {}
    role = app_meta.get("role") or "user"
    
    return {
        "id": payload.get("sub"),
        "sub": payload.get("sub"),
        "email": payload.get("email"),
        "role": str(role).lower(),
        "app_metadata": app_meta,
        "user_metadata": payload.get("user_metadata") or {},
        "raw_payload": payload
    }

def get_current_user(
    auth_creds: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Dict[str, Any]:
    """
    Verifies Supabase JWT (Authorization: Bearer <token>) and returns user identity.
    Reads role from app_metadata.role; defaults to 'user'.
    """
    if not auth_creds or not auth_creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid"
        )
    user_info = get_current_user_optional(auth_creds)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    return user_info

def require_role(required_role: str):
    """
    Enforces required role.
    Reads role exclusively from app_metadata.role (default is 'user').
    Never accepts role from request body.
    """
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = (current_user.get("role") or "user").lower()
        if user_role != required_role.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires '{required_role}' role"
            )
        return current_user
    return role_checker

def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
    return f"{salt}${key.hex()}"

def _verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, key_hex = stored_hash.split("$")
        test_key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100000)
        return hmac.compare_digest(test_key.hex(), key_hex)
    except Exception:
        return False

class AuthService:
    """Legacy helper maintained for local dev / backward compatibility."""
    @staticmethod
    def register_user(db: Session, user_in: UserRegister) -> User:
        existing = db.query(User).filter(
            (User.username == user_in.username) | (User.email == user_in.email)
        ).first()
        if existing:
            raise ValueError("User with this username or email already exists.")
        
        user = User(
            username=user_in.username,
            email=user_in.email,
            hashed_password=_hash_password(user_in.password),
            role=UserRole.USER,  # Never accept role from body
            is_active=True
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def authenticate_user(db: Session, creds: UserLogin) -> Optional[User]:
        user = db.query(User).filter(
            (User.username == creds.username_or_email) | (User.email == creds.username_or_email)
        ).first()
        if not user or not _verify_password(creds.password, user.hashed_password):
            return None
        return user

    @staticmethod
    def create_token(user: User) -> str:
        # Create a JWT token for the user so it's uniform
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "email": user.email,
            "app_metadata": {"role": user.role.value.lower()},
            "exp": int(time.time()) + 3600 * 24
        }
        secret = settings.SUPABASE_JWT_SECRET or "urbanpulse-fallback-dev-secret-key"
        return jwt.encode(payload, secret, algorithm="HS256")

    @staticmethod
    def ensure_default_roles(db: Session):
        admin = db.query(User).filter(User.username == "admin").first()
        if not admin:
            admin_user = User(
                username="admin",
                email="admin@urbanpulse.org",
                hashed_password=_hash_password("Admin@UrbanPulse2025!"),
                role=UserRole.ADMIN,
                is_active=True
            )
            db.add(admin_user)
        
        user = db.query(User).filter(User.username == "citizen").first()
        if not user:
            citizen_user = User(
                username="citizen",
                email="citizen@urbanpulse.org",
                hashed_password=_hash_password("Citizen@UrbanPulse2025!"),
                role=UserRole.USER,
                is_active=True
            )
            db.add(citizen_user)
        db.commit()
