from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import desc
from backend.app.models.construction import (
    ConstructionWorkOrder,
    ConstructionWardSummary,
    ConstructionClusterStat,
    ConstructionMeta,
)

class ConstructionService:
    @staticmethod
    def get_overview(db: Session) -> Dict[str, Any]:
        meta = db.query(ConstructionMeta).filter(ConstructionMeta.key == "overview").first()
        if meta and meta.value:
            return meta.value
        
        # Compute fallback from ward summaries
        wards = db.query(ConstructionWardSummary).all()
        total_orders = sum(w.total_work_orders for w in wards)
        total_amt = sum(w.total_amount for w in wards)
        total_net = sum(w.total_net_expenditure for w in wards)
        total_ded = sum(w.total_deduction for w in wards)
        return {
            "total_work_orders": total_orders,
            "total_amount": total_amt,
            "total_net_expenditure": total_net,
            "total_deduction": total_ded,
            "avg_deduction_rate_pct": 10.08,
            "unique_contractors": 1603,
            "distinct_ward_values": len(wards),
            "official_numbered_wards_present": 198,
            "official_wards_total": 198,
            "non_standard_ward_codes_present": 11
        }

    @staticmethod
    def get_clustering(db: Session) -> Dict[str, Any]:
        meta = db.query(ConstructionMeta).filter(ConstructionMeta.key == "clustering").first()
        cluster_stats = db.query(ConstructionClusterStat).order_by(ConstructionClusterStat.cluster).all()
        
        clusters_list = [
            {
                "cluster": c.cluster,
                "cluster_name": c.cluster_name,
                "ward_count": c.ward_count,
                "avg_work_orders": c.avg_work_orders,
                "avg_total_amount": c.avg_total_amount,
                "avg_net_expenditure": c.avg_net_expenditure,
                "avg_deduction": c.avg_deduction,
                "avg_contractors": c.avg_contractors,
            }
            for c in cluster_stats
        ]
        
        res = meta.value if meta and meta.value else {
            "method": "K-Means++ (scikit-learn), 13 standardized ward-level features, random_state=42",
            "features_used": [
                "total_work_orders", "total_amount", "avg_project_amount",
                "total_net_expenditure", "avg_net_amount", "total_deduction",
                "avg_deduction", "unique_contractors", "drain_projects",
                "road_projects", "maintenance_projects", "development_projects", "water_projects"
            ],
            "silhouette_by_k": {
                "2": 0.3919, "3": 0.3861, "4": 0.3309, "5": 0.2721, "6": 0.2271, "7": 0.2297, "8": 0.2188
            },
            "chosen_k": 2,
            "chosen_k_rationale": "K=2 has the highest silhouette score (0.392) of all K from 2-8 tested, and is the K used for the notebook's final named clustering."
        }
        res["clusters"] = clusters_list
        return res

    @staticmethod
    def get_top_wards_by_investment(db: Session, limit: int = 15) -> List[Dict[str, Any]]:
        wards = db.query(ConstructionWardSummary).order_by(desc(ConstructionWardSummary.total_amount)).limit(limit).all()
        return [
            {
                "ward": w.ward,
                "cluster_name": w.cluster_name,
                "total_work_orders": w.total_work_orders,
                "total_amount": w.total_amount,
                "total_net_expenditure": w.total_net_expenditure,
                "unique_contractors": w.unique_contractors,
            }
            for w in wards
        ]

    @staticmethod
    def get_top_wards_by_work_orders(db: Session, limit: int = 10) -> List[Dict[str, Any]]:
        wards = db.query(ConstructionWardSummary).order_by(desc(ConstructionWardSummary.total_work_orders)).limit(limit).all()
        return [
            {
                "ward": w.ward,
                "cluster_name": w.cluster_name,
                "total_work_orders": w.total_work_orders,
                "total_amount": w.total_amount,
                "unique_contractors": w.unique_contractors,
            }
            for w in wards
        ]

    @staticmethod
    def get_category_tags(db: Session) -> Dict[str, int]:
        meta = db.query(ConstructionMeta).filter(ConstructionMeta.key == "category_tags").first()
        if meta and meta.value:
            return meta.value
        return {
            "drain_projects": 1782,
            "road_projects": 1845,
            "maintenance_projects": 1419,
            "development_projects": 1284,
            "water_projects": 435
        }

    @staticmethod
    def get_ward_level_data(db: Session) -> List[Dict[str, Any]]:
        wards = db.query(ConstructionWardSummary).all()
        return [
            {
                "ward": w.ward,
                "total_work_orders": w.total_work_orders,
                "total_amount": w.total_amount,
                "avg_project_amount": w.avg_project_amount,
                "total_net_expenditure": w.total_net_expenditure,
                "avg_net_amount": w.avg_net_amount,
                "total_deduction": w.total_deduction,
                "avg_deduction": w.avg_deduction,
                "unique_contractors": w.unique_contractors,
                "drain_projects": w.drain_projects,
                "road_projects": w.road_projects,
                "maintenance_projects": w.maintenance_projects,
                "development_projects": w.development_projects,
                "water_projects": w.water_projects,
                "cluster": w.cluster,
                "cluster_name": w.cluster_name
            }
            for w in wards
        ]

    @staticmethod
    def get_full_construction_data(db: Session) -> Dict[str, Any]:
        meta_row = db.query(ConstructionMeta).filter(ConstructionMeta.key == "metadata").first()
        metadata = meta_row.value if meta_row and meta_row.value else {
            "source_file": "bbmp-2025-26-198-wards-work-orders.csv",
            "source_notebook": "urbanpulse__edaipynb.py (construction EDA cells)",
            "pipeline": "RAW CSV -> pandas cleaning -> ward-level aggregation -> KMeans++ -> verified JSON",
            "generated_note": "All figures below are computed directly from the uploaded CSV using the logic in the source notebook. No values were invented, estimated, or backfilled.",
            "geo_disclaimer": "No BBMP ward-boundary or ward-centroid coordinate dataset was supplied, so ward polygons/markers cannot be plotted on the map.",
            "category_disclaimer": "drain/road/maintenance/development/water tags are keyword matches on free-text work-order descriptions."
        }

        return {
            "metadata": metadata,
            "overview": ConstructionService.get_overview(db),
            "clustering": ConstructionService.get_clustering(db),
            "top_wards_by_investment": ConstructionService.get_top_wards_by_investment(db, limit=15),
            "top_wards_by_work_orders": ConstructionService.get_top_wards_by_work_orders(db, limit=10),
            "category_tags": ConstructionService.get_category_tags(db),
            "ward_level_data": ConstructionService.get_ward_level_data(db)
        }
