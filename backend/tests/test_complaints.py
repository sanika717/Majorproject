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


def test_admin_endpoints_auth_gate(complaints_db):
    """Verifies that non-admin gets 403 and no token gets 401 on dashboard, events, and export endpoints."""
    client = TestClient(app)
    admin_token = complaints_db["admin_token"]
    citizen_token = complaints_db["citizen_token"]

    # Submit one complaint to obtain a ticket_id
    c = client.post("/api/v1/complaints/", json={
        "category": "Roads & Potholes",
        "description": "Hazardous road section requiring attention on 80 Feet Road.",
        "location": "Indiranagar Ward 80"
    }).json()
    ticket_id = c["ticket_id"]

    endpoints = [
        f"/api/v1/complaints/admin/dashboard",
        f"/api/v1/complaints/{ticket_id}/events",
        f"/api/v1/complaints/admin/export.csv"
    ]

    for ep in endpoints:
        # 1. No token -> 401 Unauthorized
        res_no_token = client.get(ep)
        assert res_no_token.status_code == 401, f"{ep} did not return 401 without auth token"

        # 2. Citizen token (non-admin) -> 403 Forbidden
        res_citizen = client.get(ep, headers={"Authorization": f"Bearer {citizen_token}"})
        assert res_citizen.status_code == 403, f"{ep} did not return 403 with citizen token"

        # 3. Admin token -> 200 OK
        res_admin = client.get(ep, headers={"Authorization": f"Bearer {admin_token}"})
        assert res_admin.status_code == 200, f"{ep} did not return 200 with admin token"


def test_sla_overdue_computation_fixed_timestamps():
    """Verifies exact overdue computation for each priority tier using fixed timestamps."""
    from datetime import datetime, timedelta
    from backend.app.services.complaint_service import compute_sla_status

    start_time = datetime(2026, 10, 1, 10, 0, 0)

    # 1. CRITICAL: 24h SLA
    # At 23 hours: not overdue
    is_ov, h_ov = compute_sla_status("CRITICAL", "SUBMITTED", start_time, ref_time=start_time + timedelta(hours=23))
    assert not is_ov
    assert h_ov == 0.0
    # At 26.5 hours: overdue by 2.5 hours
    is_ov, h_ov = compute_sla_status("CRITICAL", "IN_PROGRESS", start_time, ref_time=start_time + timedelta(hours=26.5))
    assert is_ov
    assert h_ov == 2.5

    # 2. HIGH: 72h SLA
    # At 71 hours: not overdue
    is_ov, h_ov = compute_sla_status("HIGH", "UNDER_REVIEW", start_time, ref_time=start_time + timedelta(hours=71))
    assert not is_ov
    # At 76 hours: overdue by 4.0 hours
    is_ov, h_ov = compute_sla_status("HIGH", "UNDER_REVIEW", start_time, ref_time=start_time + timedelta(hours=76))
    assert is_ov
    assert h_ov == 4.0

    # 3. MEDIUM: 168h SLA
    # At 160 hours: not overdue
    is_ov, h_ov = compute_sla_status("MEDIUM", "SUBMITTED", start_time, ref_time=start_time + timedelta(hours=160))
    assert not is_ov
    # At 173 hours: overdue by 5.0 hours
    is_ov, h_ov = compute_sla_status("MEDIUM", "SUBMITTED", start_time, ref_time=start_time + timedelta(hours=173))
    assert is_ov
    assert h_ov == 5.0

    # 4. LOW: 336h SLA
    # At 330 hours: not overdue
    is_ov, h_ov = compute_sla_status("LOW", "SUBMITTED", start_time, ref_time=start_time + timedelta(hours=330))
    assert not is_ov
    # At 340 hours: overdue by 4.0 hours
    is_ov, h_ov = compute_sla_status("LOW", "SUBMITTED", start_time, ref_time=start_time + timedelta(hours=340))
    assert is_ov
    assert h_ov == 4.0

    # 5. Completed complaints (RESOLVED or REJECTED) are never overdue
    is_ov, h_ov = compute_sla_status("CRITICAL", "RESOLVED", start_time, ref_time=start_time + timedelta(hours=100))
    assert not is_ov
    assert h_ov == 0.0

    is_ov, h_ov = compute_sla_status("CRITICAL", "REJECTED", start_time, ref_time=start_time + timedelta(hours=100))
    assert not is_ov
    assert h_ov == 0.0


def test_status_change_writes_event_and_sets_clears_resolved_at(complaints_db):
    """Verifies ComplaintEvent creation on each status transition and resolved_at set/clear behavior."""
    client = TestClient(app)
    admin_token = complaints_db["admin_token"]
    db = complaints_db["db"]

    # 1. Submission writes initial event
    res = client.post("/api/v1/complaints/", json={
        "category": "Drainage & Flooding",
        "description": "Drain overflowing across entire road segment.",
        "location": "BTM Layout Ward 176"
    })
    assert res.status_code == 201
    ticket_id = res.json()["ticket_id"]

    events_res = client.get(f"/api/v1/complaints/{ticket_id}/events", headers={"Authorization": f"Bearer {admin_token}"})
    assert events_res.status_code == 200
    events = events_res.json()
    assert len(events) == 1
    assert events[0]["to_status"] == "SUBMITTED"
    assert events[0]["from_status"] == "SUBMITTED"

    complaint = db.query(Complaint).filter(Complaint.ticket_id == ticket_id).first()
    assert complaint.resolved_at is None

    # 2. Transition to IN_PROGRESS via admin review
    client.patch(
        f"/api/v1/complaints/{ticket_id}/admin-review",
        json={"status": "IN_PROGRESS", "admin_notes": "Assigned to storm drain engineering team."},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    db.refresh(complaint)
    assert complaint.status == ComplaintStatus.IN_PROGRESS
    assert complaint.resolved_at is None

    events = client.get(f"/api/v1/complaints/{ticket_id}/events", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert len(events) == 2
    assert events[1]["from_status"] == "SUBMITTED"
    assert events[1]["to_status"] == "IN_PROGRESS"
    assert events[1]["actor"] == "admin@urbanpulse.org"

    # 3. Transition to RESOLVED -> sets resolved_at
    client.patch(
        f"/api/v1/complaints/{ticket_id}/admin-review",
        json={"status": "RESOLVED", "admin_notes": "Drain cleared and verified."},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    db.refresh(complaint)
    assert complaint.status == ComplaintStatus.RESOLVED
    assert complaint.resolved_at is not None

    events = client.get(f"/api/v1/complaints/{ticket_id}/events", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert len(events) == 3
    assert events[2]["to_status"] == "RESOLVED"

    # 4. Move status back to UNDER_REVIEW -> clears resolved_at
    client.patch(
        f"/api/v1/complaints/{ticket_id}/status",
        json={"status": "UNDER_REVIEW", "admin_notes": "Reopening ticket due to citizen follow-up."},
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    db.refresh(complaint)
    assert complaint.status == ComplaintStatus.UNDER_REVIEW
    assert complaint.resolved_at is None

    events = client.get(f"/api/v1/complaints/{ticket_id}/events", headers={"Authorization": f"Bearer {admin_token}"}).json()
    assert len(events) == 4
    assert events[3]["from_status"] == "RESOLVED"
    assert events[3]["to_status"] == "UNDER_REVIEW"


def test_dashboard_totals_match_seeded_rows(complaints_db):
    """Verifies that GET /api/v1/complaints/admin/dashboard returns exact grouped SQL aggregates."""
    from datetime import datetime, timedelta
    client = TestClient(app)
    admin_token = complaints_db["admin_token"]
    db = complaints_db["db"]

    # Clear complaints for exact counts
    db.query(Complaint).delete()
    db.commit()

    now = datetime.utcnow()

    # Seed 1: CRITICAL open, overdue (created 30 hours ago)
    c1 = Complaint(
        ticket_id="UP-2026-TEST01",
        category="Roads & Potholes",
        description="Dangerous sinkhole",
        priority="CRITICAL",
        ward="Ward 100",
        department="BBMP Roads Infrastructure",
        status=ComplaintStatus.IN_PROGRESS,
        created_at=now - timedelta(hours=30),
        updated_at=now
    )
    # Seed 2: CRITICAL open, not overdue (created 10 hours ago)
    c2 = Complaint(
        ticket_id="UP-2026-TEST02",
        category="Safety & Policing",
        description="Hazardous power line",
        priority="CRITICAL",
        ward="Ward 100",
        department="BESCOM (Electricity Supply)",
        status=ComplaintStatus.SUBMITTED,
        created_at=now - timedelta(hours=10),
        updated_at=now
    )
    # Seed 3: HIGH, resolved within SLA (resolved in 20 hours, SLA 72h)
    c3 = Complaint(
        ticket_id="UP-2026-TEST03",
        category="Garbage & Sanitation",
        description="Garbage clearance",
        priority="HIGH",
        ward="Ward 101",
        department="BBMP Solid Waste Management",
        status=ComplaintStatus.RESOLVED,
        created_at=now - timedelta(days=2),
        resolved_at=now - timedelta(days=2) + timedelta(hours=20),
        updated_at=now
    )
    # Seed 4: LOW, rejected
    c4 = Complaint(
        ticket_id="UP-2026-TEST04",
        category="Street Lights",
        description="Request for new pole",
        priority="LOW",
        ward="Ward 102",
        department="BESCOM (Electricity Supply)",
        status=ComplaintStatus.REJECTED,
        created_at=now - timedelta(days=5),
        updated_at=now
    )
    # Seed 5: MEDIUM, under review, not overdue (created 20 hours ago, SLA 168h)
    c5 = Complaint(
        ticket_id="UP-2026-TEST05",
        category="Roads & Potholes",
        description="Minor pothole patch",
        priority="MEDIUM",
        ward="Ward 100",
        department="BBMP Roads Infrastructure",
        status=ComplaintStatus.UNDER_REVIEW,
        created_at=now - timedelta(hours=20),
        updated_at=now
    )

    db.add_all([c1, c2, c3, c4, c5])
    db.commit()

    res = client.get("/api/v1/complaints/admin/dashboard", headers={"Authorization": f"Bearer {admin_token}"})
    assert res.status_code == 200
    data = res.json()

    # Totals
    totals = data["totals"]
    assert totals["total"] == 5
    assert totals["submitted"] == 1
    assert totals["under_review"] == 1
    assert totals["in_progress"] == 1
    assert totals["resolved"] == 1
    assert totals["rejected"] == 1
    assert totals["overdue"] == 1  # Only c1 is overdue
    assert totals["critical_open"] == 2  # c1 and c2

    # SLA
    sla = data["sla"]
    assert sla["compliance_pct"] == 100.0  # c3 was resolved within SLA
    assert sla["avg_resolution_hours"] == 20.0

    # By Priority
    pri = data["by_priority"]
    assert pri["CRITICAL"] == 2
    assert pri["HIGH"] == 1
    assert pri["MEDIUM"] == 1
    assert pri["LOW"] == 1

    # Most Overdue
    most_overdue = data["most_overdue"]
    assert len(most_overdue) == 1
    assert most_overdue[0]["ticket_id"] == "UP-2026-TEST01"
    assert most_overdue[0]["hours_overdue"] > 0

    # Department open vs resolved
    dept_map = {d["label"]: d for d in data["by_department"]}
    assert dept_map["BBMP Roads Infrastructure"]["open"] == 2  # c1 and c5
    assert dept_map["BBMP Solid Waste Management"]["resolved"] == 1  # c3


def test_csv_export_excludes_identity_fields(complaints_db):
    """Verifies that export.csv honors filters and excludes all identity/contact columns and values."""
    client = TestClient(app)
    admin_token = complaints_db["admin_token"]
    db = complaints_db["db"]

    # Submit a complaint with explicit name and contact
    res = client.post("/api/v1/complaints/", json={
        "category": "Water Supply & Sewage",
        "description": "Severely contaminated municipal tap water.",
        "location": "Malleswaram Ward 65",
        "name": "Citizen Confidential Name",
        "contact": "confidential_phone_99999",
        "hide_identity": False
    })
    assert res.status_code == 201

    export_res = client.get("/api/v1/complaints/admin/export.csv", headers={"Authorization": f"Bearer {admin_token}"})
    assert export_res.status_code == 200
    assert "text/csv" in export_res.headers.get("content-type", "")

    csv_text = export_res.text
    lines = csv_text.strip().splitlines()
    header = lines[0].split(",")

    # Expected columns
    expected_header = [
        "ticket_id", "category", "ward", "department", "priority",
        "status", "created_at", "resolved_at", "is_overdue"
    ]
    assert header == expected_header

    # Ensure zero sensitive terms appear in header or data
    forbidden_terms = ["name", "contact", "phone", "email", "secret_hash", "pseudonym", "Citizen Confidential Name", "confidential_phone_99999"]
    for term in forbidden_terms:
        assert term.lower() not in csv_text.lower()

