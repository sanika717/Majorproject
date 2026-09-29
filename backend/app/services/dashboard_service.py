from typing import Dict, Any
from sqlalchemy.orm import Session
from backend.app.services.construction_service import ConstructionService
from backend.app.services.crime_service import CrimeService
from backend.app.services.police_service import PoliceService

class DashboardService:
    @staticmethod
    def get_headline_kpis(db: Session) -> Dict[str, Any]:
        cons_overview = ConstructionService.get_overview(db)
        crime_hist = CrimeService.get_historical(db)
        police_summary = PoliceService.get_summary(db)

        total_orders = cons_overview.get("total_work_orders", 4729)
        total_amt = cons_overview.get("total_amount", 31690638095)
        cr_amt = round(total_amt / 1e7, 2)
        formatted_amt = f"₹{cr_amt:,.2f} Cr"

        return {
            "kpis": {
                "total_work_orders": total_orders,
                "total_construction_investment": total_amt,
                "total_construction_investment_formatted": formatted_amt,
                "total_recorded_crimes": crime_hist.get("total_crimes", 35971),
                "crimes_period_label": f"D47 city-level total, {crime_hist.get('period_label', '2014 – 2021')}",
                "mapped_police_locations": police_summary.get("total_locations", 150),
                "highest_risk_score": crime_hist.get("highest_risk_score", 71.7),
                "highest_risk_level": crime_hist.get("highest_risk_level", "High Risk"),
                "highest_risk_year": crime_hist.get("highest_risk_year", 2016),
                "wards_covered_official": cons_overview.get("official_numbered_wards_present", 198),
                "wards_total_official": cons_overview.get("official_wards_total", 198),
                "unique_contractors": cons_overview.get("unique_contractors", 1603),
                "fatal_crimes": crime_hist.get("fatal_crimes", 5437),
                "non_fatal_crimes": crime_hist.get("non_fatal_crimes", 30534),
                "fatal_percentage": crime_hist.get("fatal_percentage", 15.11),
            },
            "active_layers": ["construction", "crime", "police"],
            "placeholder_layers": ["healthcare", "parks", "education", "transport", "utilities", "government"]
        }
