"""Bengaluru area-wise air quality (PM2.5, PM10, NO2 ...) from CPCB's real-time feed on data.gov.in.

Resource: "Real time Air Quality Index from various locations"  (id 3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69)
Page    : https://data.gov.in/resource/real-time-air-quality-index-various-locations
Needs a free data.gov.in API key in the DATA_GOV_IN_API_KEY environment variable. Without it the job is
logged as 'skipped' and nothing is stored.  Records are stored exactly as published (no gap filling).
"""
import json
import os
import urllib.parse
from datetime import datetime, timedelta
from typing import Any, Dict, Optional
from sqlalchemy.orm import Session
from backend.app.models.esg import EsgAirLive
from backend.app.services.esg_update.http import fetch, UpdateError
from backend.app.services.esg_update.provenance import ensure_source

SOURCE_CODE = "CPCB_RT_AQI"
SOURCE_NAME = "CPCB real-time AQI feed via data.gov.in (Open Government Data Platform India)"
SOURCE_URL = "https://data.gov.in/resource/real-time-air-quality-index-various-locations"
API_URL = os.environ.get("ESG_CPCB_API_URL", "https://api.data.gov.in/resource/3b01bcb8-0b14-4abf-b6f2-c1bfd384ba69")
CITY_NAMES = {"bengaluru", "bangalore", "bengaluru urban"}
SCORED = {"PM2.5": "pm25", "PM10": "pm10", "NO2": "no2"}


def _num(v) -> Optional[float]:
    try:
        f = float(str(v).strip())
        return f if f == f else None
    except (TypeError, ValueError):
        return None          # "NA", "", None -> not available; never turned into 0


def _ts(v) -> Optional[datetime]:
    for fmt in ("%d-%m-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S", "%d-%m-%Y %H:%M"):
        try:
            return datetime.strptime(str(v).strip(), fmt)
        except ValueError:
            pass
    return None


def fetch_records(api_key: str, page: int = 500, max_pages: int = 10):
    out, offset = [], 0
    for _ in range(max_pages):
        q = urllib.parse.urlencode({"api-key": api_key, "format": "json", "limit": page, "offset": offset,
                                    "filters[state]": "Karnataka"})
        try:
            body = json.loads(fetch(f"{API_URL}?{q}", timeout=45).decode("utf-8"))
        except ValueError as e:
            raise UpdateError(f"CPCB feed did not return JSON: {e}") from e
        if body.get("error"):
            raise UpdateError(f"data.gov.in error: {body['error']}")
        recs = body.get("records")
        if not isinstance(recs, list):
            raise UpdateError("unexpected response shape: no 'records' list")
        out.extend(recs)
        if len(recs) < page:
            break
        offset += page
    return out


def run(db: Session) -> Dict[str, Any]:
    key = os.environ.get("DATA_GOV_IN_API_KEY", "").strip()
    if not key:
        return {"status": "skipped", "message": "DATA_GOV_IN_API_KEY not set (free key from https://data.gov.in). No air data was fetched or invented.",
                "source_url": SOURCE_URL}
    recs = fetch_records(key)
    ensure_source(db, SOURCE_CODE)
    now = datetime.utcnow()
    ins = unch = skipped = fetched = 0
    for r in recs:
        if str(r.get("city", "")).strip().lower() not in CITY_NAMES:
            continue
        fetched += 1
        obs, station, pid = _ts(r.get("last_update")), (r.get("station") or "").strip(), (r.get("pollutant_id") or "").strip()
        if not (obs and station and pid):
            skipped += 1
            continue
        if db.query(EsgAirLive.id).filter_by(station=station, pollutant_id=pid, observed_at=obs).first():
            unch += 1
            continue
        db.add(EsgAirLive(
            station=station, city=r.get("city"), state=r.get("state"), latitude=_num(r.get("latitude")), longitude=_num(r.get("longitude")),
            pollutant_id=pid, pollutant_min=_num(r.get("pollutant_min")), pollutant_avg=_num(r.get("pollutant_avg")),
            pollutant_max=_num(r.get("pollutant_max")), observed_at=obs, source_name=SOURCE_NAME, source_url=SOURCE_URL,
            data_year=str(obs.year), last_updated=now, verification_status="official_api"))
        ins += 1
    db.commit()
    msg = f"{fetched} Bengaluru records received, {skipped} skipped (missing station/pollutant/timestamp)"
    if fetched == 0:
        msg = "feed returned no Bengaluru records for Karnataka at this time; nothing stored"
    return {"status": "ok", "fetched": fetched, "inserted": ins, "unchanged": unch, "message": msg, "source_url": SOURCE_URL}


def summary(db: Session) -> Dict[str, Any]:
    """Latest per-station readings + trailing-365-day city mean (mean of station means) for PM2.5/PM10/NO2.
    `scoring_eligible` only when the stored history covers >= ESG_LIVE_MIN_DAYS distinct days, so a few
    hourly snapshots are never presented as an annual mean."""
    min_days = int(os.environ.get("ESG_LIVE_MIN_DAYS", "90"))
    rows = db.query(EsgAirLive).order_by(EsgAirLive.observed_at.desc()).all()
    if not rows:
        return {"available": False, "scoring_eligible": False, "min_days_required": min_days, "days_covered": 0,
                "reason": "No live readings stored yet (updater has not received CPCB data).", "stations": []}
    latest: Dict[Any, EsgAirLive] = {}
    for r in rows:
        latest.setdefault((r.station, r.pollutant_id), r)
    stations: Dict[str, Dict[str, Any]] = {}
    for (st, pid), r in latest.items():
        d = stations.setdefault(st, {"station": st, "lat": r.latitude, "lng": r.longitude, "observed_at": None, "readings": {}})
        d["lat"] = d["lat"] if d["lat"] is not None else r.latitude
        d["lng"] = d["lng"] if d["lng"] is not None else r.longitude
        d["readings"][pid] = {"avg": r.pollutant_avg, "min": r.pollutant_min, "max": r.pollutant_max, "observed_at": r.observed_at.isoformat()}
        if d["observed_at"] is None or r.observed_at.isoformat() > d["observed_at"]:
            d["observed_at"] = r.observed_at.isoformat()
    newest = rows[0].observed_at
    window = [r for r in rows if r.observed_at >= newest - timedelta(days=365)]
    days = {r.observed_at.date() for r in window}
    city_mean, n_obs = {}, {}
    for pid, key in SCORED.items():
        per_station: Dict[str, list] = {}
        for r in window:
            if r.pollutant_id == pid and r.pollutant_avg is not None:
                per_station.setdefault(r.station, []).append(r.pollutant_avg)
        if per_station:
            means = [sum(v) / len(v) for v in per_station.values()]
            city_mean[key] = round(sum(means) / len(means), 2)
            n_obs[key] = sum(len(v) for v in per_station.values())
    first = min(r.observed_at for r in window).date()
    return {
        "available": True, "scoring_eligible": len(days) >= min_days and bool(city_mean), "min_days_required": min_days,
        "days_covered": len(days), "window_start": first.isoformat(), "window_end": newest.date().isoformat(),
        "period_label": f"CPCB live feed, {len(days)} days of readings to {newest.date().isoformat()}",
        "city_mean": city_mean, "observations_used": n_obs, "unit": "ug/m3",
        "method": "Mean of per-station means of stored hourly readings (trailing 365 days). Not an annual NAAQS-style mean unless the history is complete.",
        "latest_reading_at": newest.isoformat(), "last_updated": max(r.last_updated for r in rows[:200] if r.last_updated).isoformat(),
        "source": {"name": SOURCE_NAME, "url": SOURCE_URL, "verification_status": "official_api"},
        "stations": sorted(stations.values(), key=lambda s: s["station"]),
    }
