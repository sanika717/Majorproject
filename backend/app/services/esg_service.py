import json
from pathlib import Path
from typing import Any, Dict
from sqlalchemy.orm import Session
from backend.app.models.esg import (
    EsgSource, EsgAirStation, EsgCarbonEmission, EsgWaterReading, EsgElectricity,
)

DATA_DIR = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "data" / "esg"


def _load(name: str):
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def _iso(d):
    return d.isoformat() if d else None


def _version(db: Session):
    from backend.app.services.esg_update.provenance import current_version
    return current_version(db)


class EsgService:
    @staticmethod
    def seed(db: Session, force: bool = False) -> bool:
        """Load the verified JSON datasets into the DB (idempotent; skips if already seeded)."""
        if not force and db.query(EsgSource).count() > 0:
            for source_data in _load("sources.json"):
                source = db.query(EsgSource).filter_by(code=source_data["code"]).first()
                if source is None:
                    db.add(EsgSource(code=source_data["code"], title=source_data["title"],
                                     publisher=source_data.get("publisher"), url=source_data.get("url"),
                                     doi=source_data.get("doi"), period=source_data.get("period"),
                                     location=source_data.get("location"),
                                     geographic_level=source_data.get("geographic_level"),
                                     note=source_data.get("note")))
                else:
                    source.location = source_data.get("location")
                    source.geographic_level = source_data.get("geographic_level")
            db.commit()
            return False
        for m in (EsgElectricity, EsgWaterReading, EsgCarbonEmission, EsgAirStation, EsgSource):
            db.query(m).delete()
        for s in _load("sources.json"):
            db.add(EsgSource(code=s["code"], title=s["title"], publisher=s.get("publisher"), url=s.get("url"),
                             doi=s.get("doi"), period=s.get("period"), location=s.get("location"),
                             geographic_level=s.get("geographic_level"), note=s.get("note")))
        air = _load("air_quality_stations.json")
        for s in air["stations"]:
            db.add(EsgAirStation(code=s["code"], name=s["name"], category=s["category"], year=air["year"],
                                 latitude=s["lat"], longitude=s["lng"], so2=s["so2"], no2=s["no2"], pm10=s["pm10"],
                                 pm25=s["pm25"], nh3=s["nh3"], lead=s["lead"], co=s["co"], aqi=s["aqi"],
                                 source_code=air["source_code"]))
        EsgService._seed_carbon(db)
        EsgService._seed_water(db)
        e = _load("electricity_consumption.json")
        for r in e.get("rows", []):
            db.add(EsgElectricity(area=r["area"], category=r.get("category"), year=str(r["year"]),
                                  value_lakh_units=r["value_lakh_units"], source_code=r["source_code"]))
        db.commit()
        from backend.app.services.esg_update.provenance import stamp_all
        stamp_all(db)   # per-record source/date/verification columns
        return True

    @staticmethod
    def _seed_carbon(db: Session) -> None:
        c = _load("carbon_emissions.json")
        for r in c["series"]:
            db.add(EsgCarbonEmission(year=r["year"], sector=r["sector"], mmt_co2e=r["mmt_co2e"],
                                     share_pct=r["share_pct"], is_derived=False, boundary=c["boundary"],
                                     source_code=c["source_code"]))

    @staticmethod
    def _seed_water(db: Session) -> None:
        w = _load("water_quality_lakes_2020_21.json")
        for st in w["stations"]:
            for m in st["months"]:
                db.add(EsgWaterReading(station_code=st["code"], station_name=st["name"], district=st["district"],
                                       region=st["region"], month=m["m"], wq_class=m["class"], wqi_status=m["wqi"],
                                       source_code=w["source"]["code"]))

    @staticmethod
    def reseed_dataset(db: Session, job: str) -> None:
        """Reload ONE verified file-based dataset (carbon|water) without touching the others."""
        from backend.app.services.esg_update.provenance import stamp_all
        if job == "carbon":
            db.query(EsgCarbonEmission).delete()
            EsgService._seed_carbon(db)
        elif job == "water":
            db.query(EsgWaterReading).delete()
            EsgService._seed_water(db)
        else:
            raise ValueError(job)
        db.commit()
        stamp_all(db)

    @staticmethod
    def _sources(db: Session, codes) -> list:
        rows = db.query(EsgSource).filter(EsgSource.code.in_(list(codes))).all()
        return [{"code": s.code, "title": s.title, "publisher": s.publisher, "url": s.url, "doi": s.doi,
                 "period": s.period, "location": s.location, "geographic_level": s.geographic_level,
                 "note": s.note} for s in rows]

    @staticmethod
    def air_quality(db: Session) -> Dict[str, Any]:
        rows = db.query(EsgAirStation).order_by(EsgAirStation.id).all()
        air = _load("air_quality_stations.json")
        source_codes = ({r.source_code for r in rows} | {air.get("benchmark_source_code")}) - {None}
        return {"year": air["year"], "units": air["units"], "naaqs_annual": air["naaqs_annual"],
            "source_code": air["source_code"], "benchmark_source_code": air.get("benchmark_source_code"),
                "city_average": air["city_average"], "location_basis": air["location_basis"],
                "aqi_note": "AQI is not computed from annual means. aqi is null until genuine CPCB/KSPCB AQI values are imported.",
                "stations": [{"code": r.code, "name": r.name, "category": r.category, "lat": r.latitude, "lng": r.longitude,
                              "aqi": r.aqi, "so2": r.so2, "no2": r.no2, "pm10": r.pm10, "pm25": r.pm25, "nh3": r.nh3,
                              "lead": r.lead, "co": r.co, "year": r.year,
                              "source_name": r.source_name, "source_url": r.source_url, "last_updated": _iso(r.last_updated),
                              "verification_status": r.verification_status} for r in rows],
                "sources": EsgService._sources(db, source_codes),
                "live": EsgService.air_live(db), "data_version": _version(db)}

    @staticmethod
    def air_live(db: Session) -> Dict[str, Any]:
        """Latest CPCB station readings stored by the auto-update service (empty + reason if none yet)."""
        from backend.app.services.esg_update.air_cpcb import summary
        return summary(db)

    @staticmethod
    def update_status(db: Session) -> Dict[str, Any]:
        from backend.app.models.esg import EsgUpdateRun, EsgRecalcLog
        out = {}
        for job in ("air", "electricity", "carbon", "water"):
            r = db.query(EsgUpdateRun).filter_by(job=job).order_by(EsgUpdateRun.id.desc()).first()
            out[job] = None if not r else {"status": r.status, "started_at": _iso(r.started_at), "finished_at": _iso(r.finished_at),
                                           "fetched": r.fetched, "inserted": r.inserted, "updated": r.updated, "unchanged": r.unchanged,
                                           "source_url": r.source_url, "message": r.message}
        last = db.query(EsgRecalcLog).order_by(EsgRecalcLog.id.desc()).first()
        return {"jobs": out, "data_version": last.data_version if last else None,
                "last_recalculation_trigger": None if not last else {"at": _iso(last.triggered_at), "reason": last.reason}}

    @staticmethod
    def carbon(db: Session) -> Dict[str, Any]:
        rows = db.query(EsgCarbonEmission).order_by(EsgCarbonEmission.year, EsgCarbonEmission.id).all()
        dataset = _load("carbon_emissions.json")
        return {"unit": dataset["unit"], "series": [
                    {"year": r.year, "sector": r.sector,
                     "mmt_co2e": None if r.is_derived else r.mmt_co2e, "share_pct": r.share_pct,
                     "source_code": r.source_code,
                     "derived": r.is_derived, "boundary": r.boundary, "source_name": r.source_name, "source_url": r.source_url,
                     "last_updated": _iso(r.last_updated), "verification_status": r.verification_status} for r in rows],
                "years_available": sorted({r.year for r in rows}),
                "note": dataset["note"],
                "sources": EsgService._sources(db, {r.source_code for r in rows})}

    @staticmethod
    def water(db: Session) -> Dict[str, Any]:
        dataset = _load("water_quality_lakes_2020_21.json")
        rows = db.query(EsgWaterReading).filter(EsgWaterReading.region == "Bangalore Urban").all()
        mon = [r for r in rows if r.wq_class is not None]
        sat = [r for r in mon if r.wqi_status == "S"]
        classes: Dict[str, int] = {}
        for r in mon:
            classes[r.wq_class] = classes.get(r.wq_class, 0) + 1
        stations = {r.station_code for r in rows}
        scope = (dataset.get("source") or {}).get("location") or "Bangalore Urban lakes/tanks (KSPCB MINARS)"
        return {"scope": scope, "period": (dataset.get("source") or {}).get("period") or "Apr 2020 - Mar 2021",
                "stations_total": len(stations), "station_months_monitored": len(mon),
                "station_months_satisfactory": len(sat),
                "pct_satisfactory": round(len(sat) / len(mon) * 100, 2) if mon else None,
                "class_counts": dict(sorted(classes.items())),
                "satisfactory_readings": [{"station": r.station_name, "month": r.month, "class": r.wq_class} for r in sat],
                "last_updated": _iso(max((r.last_updated for r in rows if r.last_updated), default=None)),
                "verification_status": rows[0].verification_status if rows else None,
                "sources": EsgService._sources(db, {r.source_code for r in rows})}

    @staticmethod
    def electricity(db: Session) -> Dict[str, Any]:
        rows = db.query(EsgElectricity).all()
        e = _load("electricity_consumption.json")
        return {"available": len(rows) > 0, "reason": None if rows else e["reason"], "how_to_add": e["how_to_add"],
                "rows": [{"area": r.area, "category": r.category, "year": r.year, "value_lakh_units": r.value_lakh_units,
                          "source_name": r.source_name, "source_url": r.source_url, "last_updated": _iso(r.last_updated),
                          "verification_status": r.verification_status} for r in rows],
                "sources": EsgService._sources(db, {r.source_code for r in rows} | {e["reference_source_code"]})}
