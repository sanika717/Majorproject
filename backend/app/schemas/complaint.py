from typing import Optional, List
from pydantic import BaseModel
from backend.app.models.complaint import ComplaintStatus
from datetime import datetime

class ComplaintSubmit(BaseModel):
    category: str
    description: str
    location: Optional[str] = None
    name: Optional[str] = None
    contact: Optional[str] = None

class ComplaintResponse(BaseModel):
    id: int
    ticket_id: str
    category: str
    description: str
    location: Optional[str] = None
    name: Optional[str] = None
    status: ComplaintStatus
    created_at: datetime
    updated_at: datetime
    admin_notes: Optional[str] = None

    class Config:
        from_attributes = True

class ComplaintStatusUpdate(BaseModel):
    status: ComplaintStatus
    admin_notes: Optional[str] = None
