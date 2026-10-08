"""Provenance columns, source registry, data-version tracking (ESG recalculation trigger)."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from backend.app.models.esg import (
    EsgSource, EsgAirStation, EsgCarbonEmission, EsgWaterReading, EsgElectricity, EsgRecalcLog,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent.parent / "frontend" / "data" / "esg"
PROV_TABLE_MODELS = [EsgAirStation, EsgCarbonEmission, EsgWaterReading, EsgElectricity]

# how each source's records are verified
VERIFICATION = {
    "GUTTIKUNDA_2019": "peer_reviewed_paper",
    "BCAP_2019": "official_report",
    "KSPCB_MINARS_2020_21": "official_dataset",
    "CPCB_RT_AQI": "official_api",
    "BESCOM_OPENCITY": "official_dataset_republished",
}


def ensure_columns(engine) -> list:
    """Idempotent ALTER TABLE ADD COLUMN for databases created before provenance existed."""
    added = []
    insp = inspect(engine)
    for model in PROV_TABLE_MODELS:
        table = model.__table__
        if not insp.has_table(table.name):
            continue
        have = {c["name"] for c in insp.get_columns(table.name)}
        for name in ("source_name", "source_url", "data_year", "last_updated", "verification_status"):
            if name in have:
                continue
            col = table.c[name]
            ddl = f'ALTER TABLE {table.name} ADD COLUMN {name} {col.type.compile(dialect=engine.dialect)}'
            with engine.begin() as conn:
                conn.execute(text(ddl))
            added.append(f"{table.name}.{name}")
    source_table = EsgSource.__table__
    if insp.has_table(source_table.name):
        have = {c["name"] for c in insp.get_columns(source_table.name)}
        for name in ("location", "geographic_level"):
            if name in have:
                continue
            col = source_table.c[name]
            ddl = f'ALTER TABLE {source_table.name} ADD COLUMN {name} {col.type.compile(dialect=engine.dialect)}'
            with engine.begin() as conn:
                conn.execute(text(ddl))
            added.append(f"{source_table.name}.{name}")
    return added


def ensure_source(db: Session, code: str) -> Optional[EsgSource]:
    """Make sure a source listed in sources.json exists in esg_sources (DBs seeded before it was added)."""
    row = db.query(EsgSource).filter(EsgSource.code == code).first()
    if row:
        return row
    for s in json.load(open(DATA_DIR / "sources.json", encoding="utf-8")):
        if s["code"] == code:
            row = EsgSource(code=s["code"], title=s["title"], publisher=s.get("publisher"), url=s.get("url"),
                            doi=s.get("doi"), period=s.get("period"), location=s.get("location"),
                            geographic_level=s.get("geographic_level"), note=s.get("note"))
            db.add(row)
            db.flush()
            return row
    return None


def stamp_all(db: Session) -> int:
    """Fill provenance on any ESG row that lacks it, using the registered source (never invents a source)."""
    now = datetime.utcnow()
    src: Dict[str, EsgSource] = {s.code: s for s in db.query(EsgSource).all()}
    n = 0
    for model in PROV_TABLE_MODELS:
        for r in db.query(model).filter(model.source_url.is_(None)).all():
            s = src.get(r.source_code)
            if not s:
                continue
            r.source_name = s.title
            r.source_url = s.url
            r.verification_status = VERIFICATION.get(r.source_code, "unverified")
            r.data_year = str(r.year) if hasattr(r, "year") and r.year is not None else s.period
            r.last_updated = now
            n += 1
    db.commit()
    return n


def file_hash(names) -> str:
    h = hashlib.sha256()
    for n in names:
        h.update(n.encode())
        h.update((DATA_DIR / n).read_bytes())
    return h.hexdigest()


def compute_data_version(db: Session) -> str:
    """Hash of every value that feeds the ESG score or the ESG pages. Changes <=> scores must be recalculated."""
    from backend.app.services.esg_update.air_cpcb import summary as live_summary
    live = live_summary(db)
    payload = {
        "live": live.get("city_mean") if live.get("scoring_eligible") else None,
        "carbon": sorted((r.year, r.sector, r.mmt_co2e) for r in db.query(EsgCarbonEmission).all()),
        "water": [(r.station_code, r.month, r.wq_class, r.wqi_status) for r in db.query(EsgWaterReading).order_by(EsgWaterReading.id).all()],
        "air_annual": [(r.code, r.pm10, r.no2, r.pm25) for r in db.query(EsgAirStation).order_by(EsgAirStation.id).all()],
        "electricity": sorted((r.area, r.category, r.year, r.value_lakh_units) for r in db.query(EsgElectricity).all()),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:32]


def current_version(db: Session) -> Optional[str]:
    r = db.query(EsgRecalcLog).order_by(EsgRecalcLog.id.desc()).first()
    return r.data_version if r else None


def bump_if_changed(db: Session, reason: str) -> Optional[str]:
    """Record an ESG recalculation trigger when verified inputs changed. Returns new version or None."""
    new, old = compute_data_version(db), current_version(db)
    if new == old:
        return None
    db.add(EsgRecalcLog(triggered_at=datetime.utcnow(), data_version=new, previous_version=old, reason=reason))
    db.commit()
    return new
