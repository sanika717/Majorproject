from typing import List, Dict, Optional, Any
from pydantic import BaseModel

class PoliceLocationItem(BaseModel):
    id: Optional[str] = None
    name: str
    displayName: Optional[str] = None
    category: str
    lat: float
    lng: float
    icon: Optional[str] = None
    source: Optional[str] = None

class PoliceSummaryResponse(BaseModel):
    total_locations: int
    by_category: Dict[str, int]
    sources: List[str]
    disclaimer: str
