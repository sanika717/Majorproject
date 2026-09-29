from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.app.models.crime import (
    CrimeHistorical,
    CrimeRecord,
    CrimeCategoryYearSummary,
    CrimeMeta,
)

class CrimeService:
    @staticmethod
    def get_historical(db: Session) -> Dict[str, Any]:
        h = db.query(CrimeHistorical).first()
        if h:
            return {
                "period_label": h.period_label,
                "total_crimes": h.total_crimes,
                "fatal_crimes": h.fatal_crimes,
                "non_fatal_crimes": h.non_fatal_crimes,
                "fatal_percentage": h.fatal_percentage,
                "highest_risk_year": h.highest_risk_year,
                "highest_risk_score": h.highest_risk_score,
                "highest_risk_level": h.highest_risk_level,
                "highest_risk_volume_score": h.highest_risk_volume_score,
                "highest_risk_severity_score": h.highest_risk_severity_score,
            }
        return {
            "period_label": "2014 – 2021 (Up to Dec)",
            "total_crimes": 35971,
            "fatal_crimes": 5437,
            "non_fatal_crimes": 30534,
            "fatal_percentage": 15.11,
            "highest_risk_year": 2016,
            "highest_risk_score": 71.7,
            "highest_risk_level": "High Risk",
            "highest_risk_volume_score": 100.0,
            "highest_risk_severity_score": 29.26
        }

    @staticmethod
    def get_risk_formula(db: Session) -> Dict[str, Any]:
        meta = db.query(CrimeMeta).filter(CrimeMeta.key == "risk_formula").first()
        if meta and meta.value:
            return meta.value
        return {
            "description": "UrbanPulse City Crime Risk Score = (0.60 * Crime Volume Score) + (0.40 * Severity Score)",
            "volume_weight": 0.60,
            "severity_weight": 0.40,
            "thresholds": {"high": 70, "medium": 40, "low": 0}
        }

    @staticmethod
    def get_full_crime_data(db: Session) -> Dict[str, Any]:
        meta_row = db.query(CrimeMeta).filter(CrimeMeta.key == "metadata").first()
        metadata = meta_row.value if meta_row and meta_row.value else {
            "platform": "UrbanPulse",
            "title": "Smart City Transparency Platform",
            "city": "Bengaluru",
            "sources": [
                "Bengaluru City Police Annual Crime Reports (2021-2023)",
                "D47 City-level Crime Statistics Series",
                "Karnataka Police GIS KML Datasets"
            ],
            "mapped_locations_count": 150,
            "disclaimer": "Crime statistics displayed are Bengaluru city-level / division-level totals."
        }

        # Categories
        cat_meta = db.query(CrimeMeta).filter(CrimeMeta.key == "categories").first()
        if cat_meta and cat_meta.value:
            categories_dict = cat_meta.value
        else:
            categories_dict = CrimeService._build_categories_from_db(db)

        return {
            "metadata": metadata,
            "historical": CrimeService.get_historical(db),
            "risk_formula": CrimeService.get_risk_formula(db),
            "categories": categories_dict
        }

    @staticmethod
    def _build_categories_from_db(db: Session) -> Dict[str, Any]:
        # Fallback dynamic builder from records
        cats = {}
        category_titles = {
            "women": ("Crimes Against Women", "Cases"),
            "children": ("Crimes Against Children", "Cases"),
            "cyber": ("Cyber Crime by Police Division", "Cases"),
            "suicides": ("Suicides by Method & Gender", "Incidents"),
            "accidental": ("Accidental Deaths by Cause & Gender", "Incidents")
        }

        for cat_key, (title, unit) in category_titles.items():
            years_data = {}
            for yr in ["2021", "2022", "2023"]:
                recs = db.query(CrimeRecord).filter(
                    CrimeRecord.category == cat_key,
                    CrimeRecord.year == yr
                ).all()
                summary = db.query(CrimeCategoryYearSummary).filter(
                    CrimeCategoryYearSummary.category == cat_key,
                    CrimeCategoryYearSummary.year == yr
                ).first()

                items = []
                for r in recs:
                    item_dict = {}
                    if cat_key in ("women", "children"):
                        item_dict = {
                            "crime": r.item_name,
                            "reported": r.reported,
                            "detected": r.detected,
                            "detection_pct": r.detection_pct
                        }
                    elif cat_key == "cyber":
                        item_dict = {
                            "division": r.item_name,
                            "reported": r.reported,
                            "detected": r.detected,
                            "detection_pct": r.detection_pct
                        }
                    else: # suicides / accidental
                        item_dict = {
                            "cause": r.item_name,
                            "male": r.male,
                            "female": r.female,
                            "total": r.total
                        }
                    items.append(item_dict)

                yr_dict = {"items": items}
                if summary:
                    if summary.total_reported is not None:
                        yr_dict["total_reported"] = summary.total_reported
                    if summary.total_detected is not None:
                        yr_dict["total_detected"] = summary.total_detected
                    if summary.overall_detection_pct is not None:
                        yr_dict["overall_detection_pct"] = summary.overall_detection_pct
                    if summary.total_suicides is not None:
                        yr_dict["total_suicides"] = summary.total_suicides
                    if summary.total_accidental_deaths is not None:
                        yr_dict["total_accidental_deaths"] = summary.total_accidental_deaths
                    if summary.total_male is not None:
                        yr_dict["total_male"] = summary.total_male
                    if summary.total_female is not None:
                        yr_dict["total_female"] = summary.total_female
                years_data[yr] = yr_dict

            cats[cat_key] = {
                "title": title,
                "unit": unit,
                "years": years_data
            }
        return cats

    @staticmethod
    def get_crime_analytics(db: Session, category: str = "all", year: str = "2023") -> Dict[str, Any]:
        full_data = CrimeService.get_full_crime_data(db)
        
        sources_meta = {
            "all": {
                "title": "All Recorded Crimes (Historical Aggregate)",
                "source": "D47 City-level Crime Statistics series (Fatal / Non-Fatal, Bangalore City, 2014–2021 up to Dec).",
                "methodology": "Totals summed across years; Fatal % = fatal ÷ total. UrbanPulse Risk Score = 60% Volume + 40% Severity, shown for the peak year."
            },
            "women": {
                "title": "Crimes Against Women",
                "source": "Bengaluru City Police Press Note — Crimes Against Women, 2021–2023.",
                "methodology": "Reported and detected counts transcribed as published; Detection % = detected ÷ reported. City-level, not station-level."
            },
            "children": {
                "title": "Crimes Against Children",
                "source": "Bengaluru City Police Press Note — Crimes Against Children, 2021–2023.",
                "methodology": "Reported and detected counts as published; Detection % = detected ÷ reported. City-level, not station-level."
            },
            "cyber": {
                "title": "Cyber Crime by Police Division",
                "source": "Bengaluru City Police Press Note — Cyber Crime by Police Division, 2021–2023.",
                "methodology": "Division-wise reported/detected counts as published; Pending = reported − detected. Divisions are administrative, not individual stations."
            },
            "suicides": {
                "title": "Suicides by Method & Gender",
                "source": "Bengaluru City Police Press Note — Suicides & Accidental Deaths, 2021–2023.",
                "methodology": "Male/female counts by method as published; per-year method rows sum to the published total. City-level."
            },
            "accidental": {
                "title": "Accidental Deaths by Cause & Gender",
                "source": "Bengaluru City Police Press Note — Suicides & Accidental Deaths, 2021–2023.",
                "methodology": "Male/female counts by cause as published; per-year cause rows sum to the published total. City-level."
            }
        }

        meta_info = sources_meta.get(category, sources_meta["all"])
        
        if category == "all":
            h = full_data["historical"]
            return {
                "category": "all",
                "year": None,
                "title": meta_info["title"],
                "source": meta_info["source"],
                "methodology": meta_info["methodology"],
                "kpis": {
                    "total_crimes": h["total_crimes"],
                    "fatal_crimes": h["fatal_crimes"],
                    "non_fatal_crimes": h["non_fatal_crimes"],
                    "fatal_percentage": h["fatal_percentage"],
                    "period_label": h["period_label"],
                    "highest_risk_score": h["highest_risk_score"],
                    "highest_risk_level": h["highest_risk_level"],
                    "highest_risk_year": h["highest_risk_year"],
                    "highest_risk_volume_score": h["highest_risk_volume_score"],
                    "highest_risk_severity_score": h["highest_risk_severity_score"]
                },
                "items": [
                    {"type": "Fatal Cases", "count": h["fatal_crimes"]},
                    {"type": "Non-Fatal Cases", "count": h["non_fatal_crimes"]}
                ],
                "chart_data": {
                    "labels": ["Fatal", "Non-Fatal"],
                    "values": [h["fatal_crimes"], h["non_fatal_crimes"]]
                }
            }

        # Specific category + year
        cat_data = full_data.get("categories", {}).get(category, {})
        year_data = cat_data.get("years", {}).get(year, {})
        items = year_data.get("items", [])

        kpis = {}
        if category in ("women", "children", "cyber"):
            total_rep = year_data.get("total_reported", 0)
            total_det = year_data.get("total_detected", 0)
            kpis = {
                "total_reported": total_rep,
                "total_detected": total_det,
                "pending": total_rep - total_det,
                "detection_pct": year_data.get("overall_detection_pct", 0)
            }
        elif category == "suicides":
            tot = year_data.get("total_suicides", 0)
            male = year_data.get("total_male", 0)
            female = year_data.get("total_female", 0)
            kpis = {
                "total_suicides": tot,
                "male": male,
                "female": female,
                "male_share_pct": round((male / tot * 100), 1) if tot else 0
            }
        elif category == "accidental":
            tot = year_data.get("total_accidental_deaths", 0)
            male = year_data.get("total_male", 0)
            female = year_data.get("total_female", 0)
            kpis = {
                "total_accidental_deaths": tot,
                "male": male,
                "female": female,
                "male_share_pct": round((male / tot * 100), 1) if tot else 0
            }

        return {
            "category": category,
            "year": year,
            "title": f"{cat_data.get('title', category)} ({year})",
            "source": meta_info["source"],
            "methodology": meta_info["methodology"],
            "kpis": kpis,
            "items": items,
            "chart_data": {
                "items": items
            }
        }
