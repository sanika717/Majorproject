"""Electricity/energy: BESCOM annual consumption (MU) from the OpenCity CKAN portal.

Dataset : https://data.opencity.in/dataset/bescom-consumption-data   (source field: bescom.karnataka.gov.in)
The CSV columns (verified): Year, Demand (in Rs. Cr), Collection (in Rs. Cr), Consumers in Lakhs,
Consumption by Metered Category in MU, Energy Input in MU.
Scope: the BESCOM supply area (not Bengaluru city alone) - labelled as such. 1 MU = 10 lakh units.
"""
import csv
import io
import json
import os
from datetime import datetime
from typing import Any, Dict
from sqlalchemy.orm import Session
from backend.app.models.esg import EsgElectricity
from backend.app.services.esg_update.http import fetch, UpdateError, validate_esg_url
from backend.app.services.esg_update.provenance import ensure_source

SOURCE_CODE = "BESCOM_OPENCITY"
SOURCE_NAME = "BESCOM annual consumption & revenue data (bescom.karnataka.gov.in), republished by OpenCity.in"
SOURCE_URL = "https://data.opencity.in/dataset/bescom-consumption-data"
CKAN_RESOURCE_API = os.environ.get("ESG_BESCOM_CKAN_URL", "https://data.opencity.in/api/3/action/resource_show?id=addf1f15-7c90-44db-ab13-572aae08b0f1")
FALLBACK_CSV = ("https://data.opencity.in/dataset/c2e70b7b-2af9-4223-ad49-f67f32d9366f/resource/"
                "addf1f15-7c90-44db-ab13-572aae08b0f1/download/70d066f8-2145-4b98-9e94-d7657b8a04a0.csv")
AREA = "BESCOM supply area (includes Bengaluru; not Bengaluru-city only)"
COLUMNS = {"Consumption by Metered Category in MU": "Electricity consumed, metered categories (total)",
           "Energy Input in MU": "Energy input to the BESCOM system"}
MU_TO_LAKH_UNITS = 10.0


def _csv_url() -> str:
    try:
        meta = json.loads(fetch(CKAN_RESOURCE_API, timeout=30).decode("utf-8"))
        url = meta["result"]["url"]
        # Validate that the returned URL satisfies https and allowed host requirements
        validate_esg_url(url)
        return url
    except Exception:
        pass            # fall back to the last verified download URL
    return FALLBACK_CSV


def run(db: Session) -> Dict[str, Any]:
    url = _csv_url()
    text = fetch(url, timeout=45).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    missing = [c for c in ["Year", *COLUMNS] if c not in (reader.fieldnames or [])]
    if missing:
        raise UpdateError(f"CSV schema changed, missing columns {missing}; nothing stored")
    ensure_source(db, SOURCE_CODE)
    now = datetime.utcnow()
    fetched = ins = upd = unch = 0
    for row in reader:
        year = (row.get("Year") or "").strip()
        if not year:
            continue
        for col, label in COLUMNS.items():
            raw = (row.get(col) or "").strip().replace(",", "")
            try:
                lakh = round(float(raw) * MU_TO_LAKH_UNITS, 2)
            except ValueError:
                continue
            fetched += 1
            cur = db.query(EsgElectricity).filter_by(area=AREA, category=label, year=year, source_code=SOURCE_CODE).first()
            if cur is None:
                db.add(EsgElectricity(area=AREA, category=label, year=year, value_lakh_units=lakh, source_code=SOURCE_CODE,
                                      source_name=SOURCE_NAME, source_url=SOURCE_URL, data_year=year, last_updated=now,
                                      verification_status="official_dataset_republished"))
                ins += 1
            elif abs(cur.value_lakh_units - lakh) > 1e-9:
                cur.value_lakh_units, cur.last_updated = lakh, now
                upd += 1
            else:
                unch += 1
    db.commit()
    return {"status": "ok", "fetched": fetched, "inserted": ins, "updated": upd, "unchanged": unch,
        "source_url": SOURCE_URL, "message": f"CSV read from {url}"}
