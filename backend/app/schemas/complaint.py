from typing import Optional
from pydantic import BaseModel, Field
from backend.app.models.complaint import ComplaintStatus, ComplaintPriority
from datetime import datetime

class ComplaintSubmit(BaseModel):
    category: str = Field(..., max_length=100)
    description: str = Field(..., min_length=10, max_length=2000)
    location: Optional[str] = Field(None, max_length=300)
    ward: Optional[str] = Field(None, max_length=100)
    department: Optional[str] = Field(None, max_length=150)
    severity_level: Optional[int] = Field(2, ge=1, le=5)
    public_safety_impact: Optional[bool] = False
    affected_area_impact: Optional[int] = Field(2, ge=1, le=5)
    name: Optional[str] = Field(None, max_length=100)
    contact: Optional[str] = Field(None, max_length=100)
    hide_identity: Optional[bool] = False
    image_base64: Optional[str] = None  # Optional image upload with EXIF stripped

class ComplaintSubmitResponse(BaseModel):
    id: int
    ticket_id: str
    tracking_secret: Optional[str] = None  # Returned ONLY ONCE upon creation
    category: str
    description: str
    location: Optional[str] = None
    ward: Optional[str] = None
    priority: str
    department: Optional[str] = None
    severity_level: int = 2
    public_safety_impact: bool = False
    affected_area_impact: int = 2
    priority_score: int = 5
    status: ComplaintStatus
    created_at: datetime
    message: str = "Please save your tracking secret. It will not be shown again."

class ComplaintResponse(BaseModel):
    id: int
    ticket_id: str
    category: str
    description: str
    location: Optional[str] = None
    ward: Optional[str] = None
    priority: str
    department: Optional[str] = None
    severity_level: int = 2
    public_safety_impact: bool = False
    affected_area_impact: int = 2
    priority_score: int = 5
    name: Optional[str] = None  # Displays pseudonym if identity hidden and user is not owner
    status: ComplaintStatus
    created_at: datetime
    updated_at: datetime
    admin_notes: Optional[str] = None
    image_url: Optional[str] = None

    class Config:
        from_attributes = True

class ComplaintTrackRequest(BaseModel):
    ticket_id: str = Field(..., min_length=5, max_length=50)
    secret: str = Field(..., min_length=8, max_length=100)

class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    admin_notes: Optional[str] = Field(None, max_length=2000)

class ComplaintAdminUpdate(BaseModel):
    status: Optional[ComplaintStatus] = None
    department: Optional[str] = Field(None, max_length=150)
    priority: Optional[ComplaintPriority] = None
    severity_level: Optional[int] = Field(None, ge=1, le=5)
    public_safety_impact: Optional[bool] = None
    affected_area_impact: Optional[int] = Field(None, ge=1, le=5)
    admin_notes: Optional[str] = Field(None, max_length=2000)
