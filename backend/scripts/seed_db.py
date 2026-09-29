import os
import csv
import json
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR))

from backend.app.db.session import engine, Base, SessionLocal
from backend.app.models.user import User, UserRole
from backend.app.models.construction import (
    ConstructionWorkOrder,
    ConstructionWardSummary,
    ConstructionClusterStat,
    ConstructionMeta,
)
from backend.app.models.crime import (
    CrimeHistorical,
    CrimeRecord,
    CrimeCategoryYearSummary,
    CrimeMeta,
)
from backend.app.models.police import PoliceLocation
from backend.app.services.auth_service import AuthService

def seed_database():
    print("==================================================")
    print("UrbanPulse Database Seeding Script")
    print("Target DB:", engine.url)
    print("==================================================")

    # 1. Create tables
    print("[1/6] Creating database tables if not existing...")
    Base.metadata.create_all(bind=engine)
    print("✓ Tables verified.")

    db = SessionLocal()
    try:
        # 2. Seed Users / Roles
        print("[2/6] Ensuring default USER and ADMIN accounts...")
        AuthService.ensure_default_roles(db)
        print("✓ Users / roles initialized.")

        # 3. Seed Construction Data
        print("[3/6] Seeding verified Construction data...")
        cons_json_path = BASE_DIR / "data" / "construction" / "construction_data.json"
        ward_summary_csv = BASE_DIR / "data" / "construction" / "ward_level_summary.csv"
        work_orders_csv = BASE_DIR / "data" / "construction" / "bbmp-2025-26-198-wards-work-orders.csv"

        if cons_json_path.exists():
            with open(cons_json_path, "r", encoding="utf-8") as f:
                cdata = json.load(f)

            # Store metadata
            for key in ["metadata", "overview", "category_tags"]:
                if key in cdata:
                    existing_meta = db.query(ConstructionMeta).filter(ConstructionMeta.key == key).first()
                    if not existing_meta:
                        db.add(ConstructionMeta(key=key, value=cdata[key]))
                    else:
                        existing_meta.value = cdata[key]

            # Clustering meta & stats
            if "clustering" in cdata:
                clustering = cdata["clustering"]
                existing_cl_meta = db.query(ConstructionMeta).filter(ConstructionMeta.key == "clustering").first()
                if not existing_cl_meta:
                    db.add(ConstructionMeta(key="clustering", value=clustering))
                else:
                    existing_cl_meta.value = clustering

                # Clusters
                for cl in clustering.get("clusters", []):
                    existing_cl = db.query(ConstructionClusterStat).filter(ConstructionClusterStat.cluster == cl["cluster"]).first()
                    if not existing_cl:
                        db.add(ConstructionClusterStat(
                            cluster=cl["cluster"],
                            cluster_name=cl["cluster_name"],
                            ward_count=cl["ward_count"],
                            avg_work_orders=cl["avg_work_orders"],
                            avg_total_amount=cl["avg_total_amount"],
                            avg_net_expenditure=cl["avg_net_expenditure"],
                            avg_deduction=cl["avg_deduction"],
                            avg_contractors=cl["avg_contractors"]
                        ))

            db.commit()

        # Seed Ward Summaries from CSV
        if ward_summary_csv.exists() and db.query(ConstructionWardSummary).count() == 0:
            print("  -> Ingesting ward_level_summary.csv...")
            with open(ward_summary_csv, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                ward_objects = []
                for row in reader:
                    ward_objects.append(ConstructionWardSummary(
                        ward=row["ward"].strip(),
                        total_work_orders=int(row["total_work_orders"]),
                        total_amount=int(float(row["total_amount"])),
                        avg_project_amount=float(row["avg_project_amount"]),
                        total_net_expenditure=int(float(row["total_net_expenditure"])),
                        avg_net_amount=float(row["avg_net_amount"]),
                        total_deduction=int(float(row["total_deduction"])),
                        avg_deduction=float(row["avg_deduction"]),
                        unique_contractors=int(row["unique_contractors"]),
                        drain_projects=int(row.get("drain_projects", 0)),
                        road_projects=int(row.get("road_projects", 0)),
                        maintenance_projects=int(row.get("maintenance_projects", 0)),
                        development_projects=int(row.get("development_projects", 0)),
                        water_projects=int(row.get("water_projects", 0)),
                        cluster=int(row["cluster"]),
                        cluster_name=row["cluster_name"].strip()
                    ))
                db.bulk_save_objects(ward_objects)
                db.commit()
            print(f"  ✓ {len(ward_objects)} ward summaries ingested.")
        else:
            print(f"  ✓ Ward summaries already present ({db.query(ConstructionWardSummary).count()} records).")

        # Seed Work Orders from CSV (4,729 verified records)
        if work_orders_csv.exists() and db.query(ConstructionWorkOrder).count() == 0:
            print("  -> Ingesting bbmp-2025-26-198-wards-work-orders.csv (4,729 records)...")
            with open(work_orders_csv, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.DictReader(f)
                wo_objects = []
                for row in reader:
                    try:
                        amt = int(float(row.get("amount") or 0))
                        nett = int(float(row.get("nett") or 0))
                        ded = int(float(row.get("deduction") or 0))
                        slno = int(row["slno"]) if row.get("slno") and row["slno"].isdigit() else None
                        wo_objects.append(ConstructionWorkOrder(
                            slno=slno,
                            work_order_id=row.get("id", "").strip(),
                            ward=row.get("ward", "").strip(),
                            wodetails=row.get("wodetails", "").strip(),
                            contractor=row.get("contractor", "").strip() or None,
                            brnumber=row.get("brnumber", "").strip() or None,
                            amount=amt,
                            nett=nett,
                            deduction=ded
                        ))
                    except Exception as ex:
                        continue
                db.bulk_save_objects(wo_objects)
                db.commit()
            print(f"  ✓ {len(wo_objects)} construction work orders ingested.")
        else:
            print(f"  ✓ Work orders already present ({db.query(ConstructionWorkOrder).count()} records).")

        # 4. Seed Crime Data
        print("[4/6] Seeding verified Crime data...")
        crime_json_path = BASE_DIR / "data" / "crime" / "crime_data.json"
        if crime_json_path.exists():
            with open(crime_json_path, "r", encoding="utf-8") as f:
                cr_data = json.load(f)

            # Metadata & risk formula
            for key in ["metadata", "risk_formula", "categories"]:
                if key in cr_data:
                    existing_m = db.query(CrimeMeta).filter(CrimeMeta.key == key).first()
                    if not existing_m:
                        db.add(CrimeMeta(key=key, value=cr_data[key]))
                    else:
                        existing_m.value = cr_data[key]

            # Historical D47 Stats
            hist = cr_data.get("metadata", {}).get("historical_overview", {})
            if hist and db.query(CrimeHistorical).count() == 0:
                db.add(CrimeHistorical(
                    period_label=hist.get("period_label", "2014 – 2021 (Up to Dec)"),
                    total_crimes=hist.get("total_recorded_crimes", 35971),
                    fatal_crimes=hist.get("total_fatal_crimes", 5437),
                    non_fatal_crimes=hist.get("total_non_fatal_crimes", 30534),
                    fatal_percentage=float(hist.get("overall_fatal_percentage", 15.11)),
                    highest_risk_year=int(hist.get("highest_risk_year", 2016)),
                    highest_risk_score=float(hist.get("highest_risk_score", 71.7)),
                    highest_risk_level=hist.get("highest_risk_level", "High Risk"),
                    highest_risk_volume_score=100.0,
                    highest_risk_severity_score=29.26,
                    volume_weight=0.60,
                    severity_weight=0.40
                ))
                db.commit()
                print("  ✓ D47 historical stats seeded.")

            # Individual crime category items
            if db.query(CrimeRecord).count() == 0:
                records = []
                summaries = []
                categories = cr_data.get("categories", {})
                for cat_key, cat_val in categories.items():
                    years = cat_val.get("years", {})
                    for y_key, y_val in years.items():
                        # Year summary
                        summaries.append(CrimeCategoryYearSummary(
                            category=cat_key,
                            year=y_key,
                            total_reported=y_val.get("total_reported"),
                            total_detected=y_val.get("total_detected"),
                            overall_detection_pct=y_val.get("overall_detection_pct"),
                            total_suicides=y_val.get("total_suicides"),
                            total_accidental_deaths=y_val.get("total_accidental_deaths"),
                            total_male=y_val.get("total_male"),
                            total_female=y_val.get("total_female")
                        ))

                        for item in y_val.get("items", []):
                            item_name = item.get("crime") or item.get("division") or item.get("cause") or "Unknown"
                            records.append(CrimeRecord(
                                category=cat_key,
                                year=y_key,
                                item_name=item_name,
                                reported=item.get("reported"),
                                detected=item.get("detected"),
                                detection_pct=item.get("detection_pct"),
                                male=item.get("male"),
                                female=item.get("female"),
                                total=item.get("total")
                            ))
                db.bulk_save_objects(summaries)
                db.bulk_save_objects(records)
                db.commit()
                print(f"  ✓ {len(records)} category items and {len(summaries)} year summaries seeded.")
            else:
                print(f"  ✓ Crime records already present ({db.query(CrimeRecord).count()} records).")

        # 5. Seed Police Locations
        print("[5/6] Seeding verified Police locations...")
        police_json_path = BASE_DIR / "data" / "crime" / "police_locations.json"
        if police_json_path.exists() and db.query(PoliceLocation).count() == 0:
            with open(police_json_path, "r", encoding="utf-8") as f:
                locs = json.load(f)
            loc_objects = []
            for loc in locs:
                loc_objects.append(PoliceLocation(
                    location_code=loc.get("id") or f"loc-{len(loc_objects)+1}",
                    name=loc.get("name", ""),
                    display_name=loc.get("displayName") or loc.get("name", ""),
                    category=loc.get("category", "Police Station"),
                    latitude=float(loc["lat"]),
                    longitude=float(loc["lng"]),
                    icon=loc.get("icon", "shield"),
                    source=loc.get("source", "")
                ))
            db.bulk_save_objects(loc_objects)
            db.commit()
            print(f"  ✓ {len(loc_objects)} police locations ingested.")
        else:
            print(f"  ✓ Police locations already present ({db.query(PoliceLocation).count()} records).")

        # 6. Verification Summary
        print("[6/6] Verifying seeded database tables...")
        print(f"  - Users: {db.query(User).count()}")
        print(f"  - Work Orders: {db.query(ConstructionWorkOrder).count()}")
        print(f"  - Ward Summaries: {db.query(ConstructionWardSummary).count()}")
        print(f"  - Cluster Stats: {db.query(ConstructionClusterStat).count()}")
        print(f"  - Crime Historical: {db.query(CrimeHistorical).count()}")
        print(f"  - Crime Records: {db.query(CrimeRecord).count()}")
        print(f"  - Police Locations: {db.query(PoliceLocation).count()}")
        print("==================================================")
        print("UrbanPulse Database Seeding COMPLETE!")
        print("==================================================")

    except Exception as e:
        db.rollback()
        print("❌ Error during database seeding:", str(e))
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed_database()
