import hashlib
import hmac
import secrets
from typing import Optional
from sqlalchemy.orm import Session
from backend.app.models.user import User, UserRole
from backend.app.schemas.auth import UserRegister, UserLogin
from backend.app.core.config import settings

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
            role=user_in.role or UserRole.USER,
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
        # Simple, robust token format for current phase
        token_payload = f"{user.id}:{user.username}:{user.role}:{secrets.token_hex(16)}"
        return token_payload

    @staticmethod
    def ensure_default_roles(db: Session):
        # Ensure a default standard USER and ADMIN exist if not already present
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
