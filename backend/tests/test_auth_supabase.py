import time
import pytest
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.core.config import settings
from backend.app.db.session import Base, get_db
from backend.app.models.user import User, UserRole
from backend.app.services.auth_service import AuthService, _hash_password

# Test JWT secret for signing test tokens
TEST_SECRET = "test-jwt-secret-urbanpulse-super-secure-key"

@pytest.fixture
def test_db_session():
    """Provides an isolated in-memory SQLite database for auth tests."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine, tables=[User.__table__])
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = TestingSessionLocal()
    # Seed default roles
    admin = User(
        username="admin",
        email="admin@urbanpulse.org",
        hashed_password=_hash_password("AdminPass123!"),
        role=UserRole.ADMIN,
        is_active=True
    )
    citizen = User(
        username="citizen_jane",
        email="citizen.jane@urbanpulse.org",
        hashed_password=_hash_password("CitizenPass123!"),
        role=UserRole.USER,
        is_active=True
    )
    db.add(admin)
    db.add(citizen)
    db.commit()

    yield db
    db.close()

@pytest.fixture
def client(test_db_session, monkeypatch):
    """FastAPI TestClient with overridden get_db dependency and test JWT secret."""
    monkeypatch.setattr(settings, "SUPABASE_JWT_SECRET", TEST_SECRET)
    monkeypatch.setattr(settings, "SUPABASE_URL", "https://xyzcompany.supabase.co")
    monkeypatch.setattr(settings, "SUPABASE_ANON_KEY", "test-anon-key-12345")

    def override_get_db():
        try:
            yield test_db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

def create_test_token(email: str, sub: str = None, app_metadata: dict = None, user_metadata: dict = None) -> str:
    payload = {
        "sub": sub or email,
        "email": email,
        "aud": "authenticated",
        "role": "authenticated",
        "app_metadata": app_metadata or {},
        "user_metadata": user_metadata or {},
        "exp": int(time.time()) + 3600
    }
    return jwt.encode(payload, TEST_SECRET, algorithm="HS256")

def test_auth_config_endpoint(client):
    """Verifies that /auth/config returns public keys and never exposes backend secrets."""
    res = client.get("/api/v1/auth/config")
    assert res.status_code == 200
    data = res.json()
    assert data["supabase_url"] == "https://xyzcompany.supabase.co"
    assert data["supabase_anon_key"] == "test-anon-key-12345"
    assert "SUPABASE_JWT_SECRET" not in data
    assert "SUPABASE_SERVICE_ROLE_KEY" not in data

def test_get_me_unauthorized(client):
    """Accessing /auth/me without a bearer token must return 401."""
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401

def test_get_me_citizen(client):
    """Citizen user token decodes and verifies with citizen/user role."""
    token = create_test_token("citizen.jane@urbanpulse.org", sub="uuid-citizen-1")
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "authenticated"
    assert data["user"]["email"] == "citizen.jane@urbanpulse.org"
    assert data["user"]["role"] == "user"

def test_get_me_admin(client):
    """Administrator token decodes and resolves with verified admin role from database."""
    token = create_test_token("admin@urbanpulse.org", sub="uuid-admin-1")
    res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["user"]["email"] == "admin@urbanpulse.org"
    assert data["user"]["role"] == "admin"

def test_admin_check_denies_unauthenticated(client):
    """Accessing /auth/admin-check without credentials must return 401."""
    res = client.get("/api/v1/auth/admin-check")
    assert res.status_code == 401

def test_admin_check_denies_citizen(client):
    """A citizen trying to access /auth/admin-check must receive 403 Forbidden."""
    token = create_test_token("citizen.jane@urbanpulse.org", sub="uuid-citizen-1")
    res = client.get("/api/v1/auth/admin-check", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"]

def test_admin_check_permits_verified_admin(client):
    """A verified admin accessing /auth/admin-check receives 200 OK and is_admin=True."""
    token = create_test_token("admin@urbanpulse.org", sub="uuid-admin-1")
    res = client.get("/api/v1/auth/admin-check", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["is_admin"] is True
    assert data["role"] == "admin"
    assert data["user"]["email"] == "admin@urbanpulse.org"

def test_cannot_spoof_admin_role_via_token_claims(client):
    """
    Security check: Even if a malicious user crafts or self-assigns a client-side role claim,
    the server cross-verifies against the PostgreSQL database.
    """
    # A user whose email is in DB as USER
    token = create_test_token(
        "citizen.jane@urbanpulse.org",
        sub="uuid-citizen-1",
        app_metadata={"role": "admin"}  # Spoofed claim for an account that is USER in DB
    )
    res = client.get("/api/v1/auth/admin-check", headers={"Authorization": f"Bearer {token}"})
    # Since DB user citizen.jane@urbanpulse.org has role USER, DB role takes strict precedence
    assert res.status_code == 403

def test_sync_user_creates_citizen_by_default(client, test_db_session):
    """Syncing a new Supabase user creates them in the database with USER role."""
    new_email = "newbie.resident@bengaluru.in"
    token = create_test_token(
        new_email,
        sub="uuid-newbie-99",
        user_metadata={"full_name": "New Resident"}
    )
    res = client.post("/api/v1/auth/sync", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "synced"
    assert data["user"]["email"] == new_email
    assert data["user"]["role"] == "USER"

    # Verify directly in database
    db_user = test_db_session.query(User).filter(User.email == new_email).first()
    assert db_user is not None
    assert db_user.role == UserRole.USER
