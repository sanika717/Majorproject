from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.db.session import get_db
from backend.app.db.session import SessionLocal
from backend.app.services.esg_service import EsgService
from backend.app.services.esg_update import run_job, JOBS
from backend.app.services.auth_service import require_role
from backend.app.core.config import settings
from datetime import datetime, timezone
import zoneinfo
import httpx

router = APIRouter(prefix="/esg", tags=["ESG"])


def _calc_cpcb_aqi(pm25: float | None, pm10: float | None):
    def sub(v, bp):
        if v is None:
            return 0
        for b_lo, b_hi, i_lo, i_hi in bp:
            if b_lo <= v <= b_hi:
                return round(i_lo + (i_hi - i_lo) * (v - b_lo) / (b_hi - b_lo))
        if v > bp[-1][1]:
            b_lo, b_hi, i_lo, i_hi = bp[-1]
            return round(i_hi + (v - b_hi))
        return 0

    bp_pm25 = [(0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200), (91, 120, 201, 300), (121, 250, 301, 400), (251, 350, 401, 500)]
    bp_pm10 = [(0, 50, 0, 50), (51, 100, 51, 100), (101, 250, 101, 200), (251, 350, 201, 300), (351, 430, 301, 400), (431, 500, 401, 500)]
    i25 = sub(pm25, bp_pm25)
    i10 = sub(pm10, bp_pm10)
    score = max(i25, i10)
    cats = [(50, "Good"), (100, "Satisfactory"), (200, "Moderate"), (300, "Poor"), (400, "Very Poor"), (float("inf"), "Severe")]
    cat = next(c[1] for c in cats if score <= c[0])
    dom = "PM2.5" if i25 >= i10 else "PM10"
    return score, cat, dom


def _format_ist_full(dt_input):
    if not dt_input:
        return "—"
    try:
        if isinstance(dt_input, str):
            clean = dt_input.replace("Z", "").split("+")[0]
            dt = datetime.fromisoformat(clean)
        else:
            import zoneinfo
            dt = dt_input.astimezone(zoneinfo.ZoneInfo("Asia/Kolkata"))
        return dt.strftime("%d %b %Y, %A, %I:%M %p IST")
    except Exception:
        return str(dt_input)


@router.get("/aqi")
async def get_live_aqi():
    """
    Fetches genuine live AQI and hourly PM2.5 / PM10 timeline for Bengaluru (12.9716°N, 77.5946°E).
    Uses Google Air Quality API if GOOGLE_AQI_API_KEY is configured in .env,
    and Open-Meteo / Copernicus CAMS atmospheric monitoring API for real-time and 24h timeline.
    All data is generated dynamically from live API requests without any mock or hardcoded numbers.
    """
    from datetime import datetime, timezone
    import zoneinfo

    key = settings.GOOGLE_AQI_API_KEY
    open_meteo_url = (
        "https://air-quality-api.open-meteo.com/v1/air-quality?"
        "latitude=12.9716&longitude=77.5946&"
        "current=european_aqi,us_aqi,pm10,pm2_5,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone&"
        "hourly=pm10,pm2_5,us_aqi&timezone=Asia%2FKolkata&past_days=1&forecast_days=1"
    )

    fetch_time_utc = datetime.now(timezone.utc)
    fetch_time_formatted = _format_ist_full(fetch_time_utc)

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 1. Fetch Open-Meteo live atmospheric feed for Bengaluru
            om_resp = await client.get(open_meteo_url, headers={"User-Agent": "UrbanPulse/1.0"})
            if not om_resp.is_success:
                raise HTTPException(status_code=502, detail=f"Open-Meteo API returned status {om_resp.status_code}")
            om_data = om_resp.json()

            curr = om_data.get("current", {})
            hourly = om_data.get("hourly", {})

            pm25 = curr.get("pm2_5")
            pm10 = curr.get("pm10")
            cpcb_score, cpcb_cat, cpcb_dom = _calc_cpcb_aqi(pm25, pm10)

            # Build past 24 hours timeline up to current hour
            times = hourly.get("time", [])
            pm25_series = hourly.get("pm2_5", [])
            pm10_series = hourly.get("pm10", [])

            curr_time_str = curr.get("time") or ""
            data_time_formatted = _format_ist_full(curr_time_str)

            curr_idx = len(times) - 1
            for idx, t in enumerate(times):
                if t >= curr_time_str:
                    curr_idx = idx
                    break

            start_idx = max(0, curr_idx - 23)
            timeline = []
            for i in range(start_idx, curr_idx + 1):
                raw_t = times[i]
                hour_label = raw_t.split("T")[-1] if "T" in raw_t else raw_t
                timeline.append({
                    "raw_time": raw_t,
                    "label": hour_label,
                    "formatted_time": _format_ist_full(raw_t),
                    "pm25": pm25_series[i] if i < len(pm25_series) else None,
                    "pm10": pm10_series[i] if i < len(pm10_series) else None
                })

            # Check if Google AQI key is configured to optionally enrich with Google's UAQI
            google_aqi = None
            google_cat = None
            if key:
                try:
                    g_url = f"https://airquality.googleapis.com/v1/currentConditions:lookup?key={key}"
                    g_payload = {
                        "location": {"latitude": 12.9716, "longitude": 77.5946},
                        "languageCode": "en"
                    }
                    g_resp = await client.post(g_url, json=g_payload, timeout=5)
                    if g_resp.is_success:
                        g_data = g_resp.json()
                        for idx_item in g_data.get("indexes", []):
                            if idx_item.get("code") == "uaqi":
                                google_aqi = idx_item.get("aqi")
                                google_cat = idx_item.get("category")
                                break
                except Exception:
                    pass

            active_aqi = google_aqi if google_aqi is not None else cpcb_score
            active_cat = google_cat if google_cat is not None else cpcb_cat
            source_label = "Google Air Quality API · Bengaluru" if google_aqi is not None else "Open-Meteo / Copernicus CAMS · Bengaluru"

            return {
                "status": "ok",
                "aqi": active_aqi,
                "category": active_cat,
                "cpcb_aqi": cpcb_score,
                "us_aqi": curr.get("us_aqi"),
                "pm25": pm25,
                "pm10": pm10,
                "dominantPollutant": f"{cpcb_dom} ({pm25 if cpcb_dom == 'PM2.5' else pm10} µg/m³)",
                "data_timestamp": curr_time_str,
                "data_timestamp_formatted": data_time_formatted,
                "fetch_timestamp": fetch_time_utc.isoformat(),
                "fetch_timestamp_formatted": fetch_time_formatted,
                "dateTime": curr_time_str,
                "source": source_label,
                "timeline": timeline,
                "keyConfigured": bool(key)
            }
    except Exception as exc:
        return {
            "status": "error",
            "error": str(exc),
            "message": "Live air quality API currently unavailable. Please check connectivity."
        }


@router.get("/air-quality")
def get_air_quality(db: Session = Depends(get_db)):
    """Area-wise (station-wise) ambient air pollutant data with source and year."""
    return EsgService.air_quality(db)


@router.get("/carbon-emissions")
def get_carbon_emissions(db: Session = Depends(get_db)):
    """Bengaluru GHG emissions by year/sector (only years with an official inventory)."""
    return EsgService.carbon(db)


@router.get("/water-quality")
def get_water_quality(db: Session = Depends(get_db)):
    """KSPCB lake/tank water-quality summary for Bangalore Urban."""
    return EsgService.water(db)


@router.get("/electricity")
def get_electricity(db: Session = Depends(get_db)):
    """Electricity consumption by area/year; empty with a reason when no genuine data is imported."""
    return EsgService.electricity(db)


@router.post("/reseed", dependencies=[Depends(require_role("admin"))])
def reseed(db: Session = Depends(get_db)):
    """Reload ESG tables from frontend/data/esg/*.json (Admin only)."""
    result = {"reseeded": EsgService.seed(db, force=True)}
    run_job("electricity", SessionLocal, force=True)   # reseed clears auto-fetched rows; fetch them again
    return result


@router.get("/update-status")
def update_status(db: Session = Depends(get_db)):
    """Last run of each auto-update job + current ESG data version (changes => scores recalculated)."""
    return EsgService.update_status(db)


@router.post("/update-now", dependencies=[Depends(require_role("admin"))])
def update_now(job: str = "all"):
    """Run one auto-update job (air|electricity|carbon|water) or all of them immediately (Admin only)."""
    if job != "all" and job not in JOBS:
        raise HTTPException(400, f"job must be one of {list(JOBS)} or 'all'")
    return [run_job(j, SessionLocal, force=True) for j in (JOBS if job == "all" else [job])]
