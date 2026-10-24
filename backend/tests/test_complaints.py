import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.main import app
from backend.app.db.session import Base, get_db
from backend.app.models.user import User, UserRole
from backend.app.models.complaint import Complaint, ComplaintContact, ComplaintStatus, ComplaintPriority, ensure_complaint_columns
from backend.app.services.auth_service import AuthService, _hash_password
from backend.app.services.complaint_service import calculate_priority_score

@pytest.fixture
def complaints_db():
    """Provides an isolated SQLite database for complaints backend tests."""
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = TestingSessionLocal()

    # Seed admin and citizen users
    admin = User(
        username="admin",
        email="admin@urbanpulse.org",
        hashed_password=_hash_password("AdminPass123!"),
        role=UserRole.ADMIN,
        is_active=True
    )
    citizen = User(
        username="citizen_ramesh",
        email="ramesh@example.com",
        hashed_password=_hash_password("CitizenPass123!"),
        role=UserRole.USER,
        is_active=True
    )
    db.add(admin)
    db.add(citizen)
    db.commit()
    db.refresh(admin)
    db.refresh(citizen)

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    yield {
        "db": db,
        "admin": admin,
        "citizen": citizen,
        "admin_token": AuthService.create_token(admin),
        "citizen_token": AuthService.create_token(citizen)
    }

    app.dependency_overrides.clear()
    db.close()

def test_priority_calculation_formula():
    """Validates the objective prioritization matrix formula."""
    # Low severity, localized, no safety hazard
    score, pri = calculate_priority_score(severity=1, public_safety=False, area_impact=1)
    assert score == 4  # (1*2) + 0 + (1*1.5) = 3.5 -> 4
    assert pri == ComplaintPriority.LOW

    # Medium severity, neighborhood impact, no safety hazard
    score, pri = calculate_priority_score(severity=3, public_safety=False, area_impact=3)
    assert score == 11  # (3*2) + 0 + (3*1.5) = 10.5 -> 11
    assert pri == ComplaintPriority.HIGH

    # Critical: severe hazard with public safety threat
    score, pri = calculate_priority_score(severity=4, public_safety=True, area_impact=3)
    assert score == 18  # (4*2) + 5 + (3*1.5) = 17.5 -> 18
    assert pri == ComplaintPriority.CRITICAL

def test_complaint_submission_workflow(complaints_db):
    """Citizen submits a grievance; verifies database persistence, ticket generation, and secret code."""
    client = TestClient(app)

    payload = {
        "category": "Roads & Potholes",
        "description": "Massive crater on 100 Feet Road Indiranagar causing severe vehicle damage and traffic bottleneck.",
        "location": "100 Feet Road, Indiranagar, Ward 80",
        "name": "Ramesh Kumar",
        "contact": "ramesh@example.com",
        "hide_identity": False
    }

    res = client.post("/api/v1/complaints/", json=payload)
    assert res.status_code == 201
    data = res.json()

    assert data["ticket_id"].startswith("UP-")
    assert len(data["tracking_secret"]) >= 24
    assert data["category"] == "Roads & Potholes"
    assert data["department"] == "BBMP Roads Infrastructure"
    assert data["status"] == "SUBMITTED"
    assert data["priority"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    # Verify database isolation: contact info stored in complaint_contacts, not complaints table
    db = complaints_db["db"]
    complaint = db.query(Complaint).filter(Complaint.ticket_id == data["ticket_id"]).first()
    assert complaint is not None
    assert complaint.description == payload["description"]
    # Secret must be hashed with SHA-256 in the database (never stored in plaintext)
    assert complaint.secret_hash is not None
    assert complaint.secret_hash != data["tracking_secret"]

    contact = db.query(ComplaintContact).filter(ComplaintContact.complaint_id == complaint.id).first()
    assert contact is not None
    assert contact.name == "Ramesh Kumar"
    assert contact.contact == "ramesh@example.com"

def test_complaint_anonymity_and_pseudonym(complaints_db):
    """Submitting with hide_identity=True assigns a randomized pseudonym and shields citizen identity."""
    client = TestClient(app)

    payload = {
        "category": "Garbage & Sanitation",
        "description": "Illegal municipal waste dumping on open plot near lake boundary.",
        "location": "Bellandur Ward 150",
        "name": "Confidential Informant",
        "contact": "informant@private.org",
        "hide_identity": True
    }

    res = client.post("/api/v1/complaints/", json=payload)
    assert res.status_code == 201
    ticket_id = res.json()["ticket_id"]
    secret = res.json()["tracking_secret"]

    # Track complaint
    track_res = client.post("/api/v1/complaints/track", json={"ticket_id": ticket_id, "secret": secret})
    assert track_res.status_code == 200
    track_data = track_res.json()
    assert track_data["name"].startswith("Citizen ")  # Pseudonym used
    assert "Confidential Informant" not in track_data["name"]

def test_secure_ticket_tracking(complaints_db):
    """Tracking requires both ticket ID and exact secret code."""
    client = TestClient(app)

    # 1. Submit
    res = client.post("/api/v1/complaints/", json={
        "category": "Street Lights",
        "description": "All street lamps non-functional along 5th Main HSR Layout for 3 consecutive days.",
        "location": "HSR Layout Sector 2"
    })
    assert res.status_code == 201
    ticket_id = res.json()["ticket_id"]
    secret = res.json()["tracking_secret"]

    # 2. Track with correct credentials
    valid_track = client.post("/api/v1/complaints/track", json={"ticket_id": ticket_id, "secret": secret})
    assert valid_track.status_code == 200
    assert valid_track.json()["ticket_id"] == ticket_id
    assert valid_track.json()["status"] == "SUBMITTED"

    # 3. Track with wrong secret
    wrong_track = client.post("/api/v1/complaints/track", json={"ticket_id": ticket_id, "secret": "wrong-secret-token-value-12345"})
    assert wrong_track.status_code == 404

    # 4. Track with non-existent ticket
    not_found_track = client.post("/api/v1/complaints/track", json={"ticket_id": "UP-2026-ZZZZZZ", "secret": secret})
    assert not_found_track.status_code == 404

def test_public_feed_and_stats(complaints_db):
    """Public feed returns real complaints stripped of PII; stats reflect exact database counts."""
    client = TestClient(app)

    # Clean initial state: stats show 0
    stats0 = client.get("/api/v1/complaints/stats").json()
    assert stats0["total"] == 0

    # Add 2 complaints
    c1 = client.post("/api/v1/complaints/", json={
        "category": "Water Supply & Sewage",
        "description": "Contaminated drinking water with brown sediment flowing in residential taps.",
        "location": "Malleswaram 8th Cross",
        "name": "Secret Person",
        "contact": "personal_phone_99999"
    }).json()

    c2 = client.post("/api/v1/complaints/", json={
        "category": "Drainage & Flooding",
        "description": "Storm drain clogged with construction debris causing localized waterlogging.",
        "location": "Koramangala 4th Block"
    }).json()

    # Verify Stats
    stats = client.get("/api/v1/complaints/stats").json()
    assert stats["total"] == 2
    assert stats["by_status"]["SUBMITTED"] == 2
    assert "Water Supply & Sewage" in stats["by_category"]

    # Verify Public Feed
    feed_res = client.get("/api/v1/complaints/public?limit=10")
    assert feed_res.status_code == 200
    feed = feed_res.json()
    assert len(feed) == 2
    # Ensure zero contact details or private fields are present in public feed
    for item in feed:
        assert "name" not in item
        assert "contact" not in item
        assert "secret_hash" not in item
        assert "user_id" not in item
        assert item["ticket_id"] in [c1["ticket_id"], c2["ticket_id"]]

def test_admin_authority_review_workflow(complaints_db):
    """Authority reviews complaint, updates status, reassigns department, adjusts prioritization factors, and adds notes."""
    client = TestClient(app)
    admin_token = complaints_db["admin_token"]
    citizen_token = complaints_db["citizen_token"]

    # 1. Citizen creates a complaint
    c = client.post("/api/v1/complaints/", json={
        "category": "Safety & Policing",
        "description": "Defective traffic signals causing near misses at major junction.",
        "location": "Sony World Signal, Koramangala"
    }).json()
    ticket_id = c["ticket_id"]
    secret = c["tracking_secret"]

    # 2. Non-admin attempting admin review is blocked (403 Forbidden)
    forbidden_res = client.patch(
        f"/api/v1/complaints/{ticket_id}/admin-review",
        json={"status": "IN_PROGRESS"},
        headers={"Authorization": f"Bearer {citizen_token}"}
    )
    assert forbidden_res.status_code == 403

    # 3. Verified Admin reviews complaint:
    # Set status to IN_PROGRESS, assign to police traffic division, mark public safety hazard
    review_payload = {
        "status": "IN_PROGRESS",
        "department": "Bengaluru City Police - Traffic Management Center",
        "severity_level": 4,
        "public_safety_impact": True,
        "affected_area_impact": 4,
        "admin_notes": "Traffic engineering team dispatched. Manual traffic management deployed during signal repair."
    }

    admin_res = client.patch(
        f"/api/v1/complaints/{ticket_id}/admin-review",
        json=review_payload,
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert admin_res.status_code == 200
    updated = admin_res.json()

    assert updated["status"] == "IN_PROGRESS"
    assert updated["department"] == "Bengaluru City Police - Traffic Management Center"
    assert updated["priority"] == "CRITICAL"  # Automatically elevated due to safety hazard (score = 4*2 + 5 + 4*1.5 = 19)
    assert updated["admin_notes"] == review_payload["admin_notes"]

    # 4. Citizen tracking immediately observes authority update
    tracked = client.post("/api/v1/complaints/track", json={"ticket_id": ticket_id, "secret": secret}).json()
    assert tracked["status"] == "IN_PROGRESS"
    assert tracked["department"] == "Bengaluru City Police - Traffic Management Center"
    assert tracked["admin_notes"] == review_payload["admin_notes"]
    assert tracked["priority"] == "CRITICAL"
