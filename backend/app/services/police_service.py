from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models.police import PoliceLocation

class PoliceService:
    @staticmethod
    def get_all_locations(db: Session, category: Optional[str] = None) -> List[Dict[str, Any]]:
        query = db.query(PoliceLocation)
        if category:
            query = query.filter(PoliceLocation.category == category)
        
        locations = query.order_by(PoliceLocation.id).all()
        return [
            {
                "id": loc.location_code,
                "name": loc.name,
                "displayName": loc.display_name,
                "category": loc.category,
                "lat": loc.latitude,
                "lng": loc.longitude,
                "icon": loc.icon,
                "source": loc.source
            }
            for loc in locations
        ]

    @staticmethod
    def get_summary(db: Session) -> Dict[str, Any]:
        locations = db.query(PoliceLocation).all()
        by_category = {}
        sources = set()

        for loc in locations:
            by_category[loc.category] = by_category.get(loc.category, 0) + 1
            if loc.source:
                sources.add(loc.source)

        return {
            "total_locations": len(locations),
            "by_category": by_category,
            "sources": sorted(list(sources)),
            "disclaimer": "Pins show official station locations only. No station-level crime counts exist in the supplied data, so none are displayed."
        }
