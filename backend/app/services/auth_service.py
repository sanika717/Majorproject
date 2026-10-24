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
    Supports:
    1. Symmetric HS256 secret (SUPABASE_JWT_SECRET).
    2. JWKS endpoint (asymmetric RS256/ES256) via SUPABASE_URL.
    3. Direct Supabase Auth API verification (/auth/v1/user) if secret validation fails.
    4. Development fallback if ENV == 'dev' and no secrets configured.
    """
    # 1. Try symmetric HS256 if SUPABASE_JWT_SECRET is set
    if settings.SUPABASE_JWT_SECRET:
        try:
            return jwt.decode(
                token,
                settings.SUPABASE_JWT_SECRET,
                algorithms=["HS256"],
                options={"verify_aud": False}
            )
        except Exception as e:
            # If secret fails, try JWKS or Supabase Auth API before giving up
            pass

    # 2. Try JWKS if asymmetric or SUPABASE_URL configured
    try:
        unverified_header = jwt.get_unverified_header(token)
        alg = unverified_header.get("alg", "HS256")
        if alg in ["RS256", "ES256"] or not settings.SUPABASE_JWT_SECRET:
            jwks = _get_jwks_client()
            if jwks:
                signing_key = jwks.get_signing_key_from_jwt(token)
                return jwt.decode(
                    token,
                    signing_key.key,
                    algorithms=[alg],
                    options={"verify_aud": False}
                )
    except Exception:
        pass

    # 3. Direct verification via Supabase Auth API
    if settings.SUPABASE_URL:
        try:
            headers = {"Authorization": f"Bearer {token}"}
            if settings.SUPABASE_ANON_KEY:
                headers["apikey"] = settings.SUPABASE_ANON_KEY
            verify_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/user"
            resp = requests.get(verify_url, headers=headers, timeout=5)
            if resp.status_code == 200:
                user_data = resp.json()
                return {
                    "sub": user_data.get("id"),
                    "id": user_data.get("id"),
                    "email": user_data.get("email"),
                    "app_metadata": user_data.get("app_metadata") or {},
                    "user_metadata": user_data.get("user_metadata") or {},
                    "aud": user_data.get("aud", "authenticated")
                }
        except Exception:
            pass

    # 4. In dev mode without configured secrets, allow unverified decode for inspection
    if settings.ENV == "dev":
        try:
            return jwt.decode(token, options={"verify_signature": False, "verify_aud": False})
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Could not parse token: {str(e)}"
            )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired authentication token."
    )

def get_current_user_optional(
    auth_creds: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Optional[Dict[str, Any]]:
    """
    Optional user dependency for routes accessible both anonymously and authenticated.
    Verifies token, checks database role, and resolves user identity.
    """
    if not auth_creds or not auth_creds.credentials:
        return None
    token = auth_creds.credentials
    payload = decode_supabase_jwt(token)
    
    email = payload.get("email")
    sub = payload.get("sub") or payload.get("id")
    app_meta = payload.get("app_metadata") or {}
    
    # Secure role determination: check PostgreSQL database first, then trusted app_metadata
    resolved_role = "user"
    db_user = None
    if email:
        db_user = db.query(User).filter(User.email == email).first()
    if not db_user and sub:
        db_user = db.query(User).filter(User.username == sub).first()

    if db_user:
        resolved_role = db_user.role.value.lower()
    else:
        # Check app_metadata (cannot be modified by client)
        if app_meta.get("role"):
            resolved_role = str(app_meta.get("role")).lower()
    
    return {
        "id": sub,
        "sub": sub,
        "email": email,
        "role": resolved_role,
        "app_metadata": app_meta,
        "user_metadata": payload.get("user_metadata") or {},
        "raw_payload": payload,
        "db_user_id": db_user.id if db_user else None
    }

def get_current_user(
    auth_creds: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Verifies Supabase JWT (Authorization: Bearer <token>) and returns verified user identity.
    Validates role against the database or trusted claims.
    """
    if not auth_creds or not auth_creds.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header missing or invalid"
        )
    user_info = get_current_user_optional(auth_creds, db=db)
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials or expired session"
        )
    return user_info

def require_role(required_role: str):
    """
    Enforces required role based strictly on verified database record or trusted app_metadata.
    Never accepts role from user-controlled client requests.
    """
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = (current_user.get("role") or "user").lower()
        if user_role != required_role.lower():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: requires verified '{required_role}' privileges."
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

    @staticmethod
    def sync_supabase_user(db: Session, user_info: Dict[str, Any]) -> User:
        """
        Synchronizes an authenticated Supabase user into the local PostgreSQL database.
        Strictly preserves existing roles; new accounts always receive USER role
        unless app_metadata.role is explicitly 'admin'.
        """
        email = user_info.get("email")
        if not email:
            raise ValueError("Email is required to sync user account.")

        user = db.query(User).filter(User.email == email).first()
        if not user:
            user_meta = user_info.get("user_metadata") or {}
            username_candidate = email.split("@")[0][:45]
            base_name = username_candidate
            counter = 1
            while db.query(User).filter(User.username == username_candidate).first():
                username_candidate = f"{base_name[:40]}_{counter}"
                counter += 1

            app_meta = user_info.get("app_metadata") or {}
            role = UserRole.ADMIN if str(app_meta.get("role", "")).lower() == "admin" else UserRole.USER

            user = User(
                username=username_candidate,
                email=email,
                hashed_password=_hash_password(secrets.token_hex(24)),
                role=role,
                is_active=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user
