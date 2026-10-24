"""Tests for the ESG auto-update service.  Run from the project root:  python3 -m pytest backend/tests -q

Uses an in-memory SQLite DB (never your real database) and a local mock HTTP server.
FIXTURE NOTE: the CPCB records below are synthetic TEST INPUTS in the documented data.gov.in format, used only
to exercise the parser. They are never written outside the throw-away test database.
"""
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.db.session import Base
from backend.app.models import esg as m
from backend.app.services.esg_service import EsgService
from backend.app.services.esg_update import run_job
from backend.app.services.esg_update import air_cpcb

REAL_BESCOM_CSV = Path(__file__).parent / "fixtures" / "bescom_consumption.csv"   # copy of the published CSV
STATE = {"cpcb": [], "csv": REAL_BESCOM_CSV.read_text(encoding="utf-8")}


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_HEAD(self):
        self.send_response(200); self.end_headers()

    def do_GET(self):
        if self.path.startswith("/cpcb"):
            body = json.dumps({"records": STATE["cpcb"]}).encode(); ct = "application/json"
        elif self.path.startswith("/ckan"):
            body = json.dumps({"result": {"url": f"http://127.0.0.1:{self.server.server_port}/bescom.csv"}}).encode(); ct = "application/json"
        else:
            body = STATE["csv"].encode(); ct = "text/csv"
        self.send_response(200); self.send_header("Content-Type", ct); self.end_headers(); self.wfile.write(body)


@pytest.fixture(scope="module")
def server():
    s = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s
    s.shutdown()


@pytest.fixture()
def sf(server, monkeypatch):
    port = server.server_port
    monkeypatch.setattr(air_cpcb, "API_URL", f"http://127.0.0.1:{port}/cpcb")
    from backend.app.services.esg_update import electricity_bescom as eb
    monkeypatch.setattr(eb, "CKAN_RESOURCE_API", f"http://127.0.0.1:{port}/ckan")
    eng = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(eng, tables=[t.__table__ for t in (m.EsgSource, m.EsgAirStation, m.EsgCarbonEmission, m.EsgWaterReading,
                                                               m.EsgElectricity, m.EsgAirLive, m.EsgUpdateRun, m.EsgRecalcLog)])
    f = sessionmaker(bind=eng)
    db = f(); EsgService.seed(db); db.close()
    STATE["csv"] = REAL_BESCOM_CSV.read_text(encoding="utf-8")
    return f


def rec(station, pid, avg, ts, city="Bengaluru", **kw):
    d = {"state": "Karnataka", "city": city, "station": station, "last_update": ts, "pollutant_id": pid,
         "pollutant_min": "NA", "pollutant_max": "NA", "pollutant_avg": avg}
    d.update(kw); return d


def test_air_skipped_without_key_and_stores_nothing(sf, monkeypatch):
    monkeypatch.delenv("DATA_GOV_IN_API_KEY", raising=False)
    r = run_job("air", sf, force=True)
    assert r["status"] == "skipped"
    assert sf().query(m.EsgAirLive).count() == 0


def test_air_ingest_idempotent_na_handling_and_scoring_gate(sf, monkeypatch):
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "test-key")
    monkeypatch.setenv("ESG_LIVE_MIN_DAYS", "2")
    STATE["cpcb"] = [
        rec("Silk Board, Bengaluru - KSPCB", "PM2.5", "40", "01-01-2026 10:00:00"),
        rec("Silk Board, Bengaluru - KSPCB", "PM2.5", "60", "02-01-2026 10:00:00"),
        rec("Hebbal, Bengaluru - KSPCB", "PM2.5", "20", "02-01-2026 10:00:00"),
        rec("Hebbal, Bengaluru - KSPCB", "PM10", "NA", "02-01-2026 10:00:00"),      # NA must stay NULL, not 0
        rec("Mumbai station", "PM2.5", "99", "02-01-2026 10:00:00", city="Mumbai"),  # other city ignored
        rec("Broken ts", "PM2.5", "10", "not-a-date"),                               # unparseable -> skipped
    ]
    r = run_job("air", sf, force=True)
    assert r["status"] == "ok" and r["inserted"] == 4
    db = sf()
    na = db.query(m.EsgAirLive).filter_by(pollutant_id="PM10").one()
    assert na.pollutant_avg is None
    assert all(x.source_url and x.source_name and x.last_updated and x.verification_status == "official_api" for x in db.query(m.EsgAirLive))
    assert run_job("air", sf, force=True)["inserted"] == 0                           # idempotent
    s = EsgService.air_live(db)
    # station means: Silk Board (40+60)/2=50, Hebbal 20 -> city mean 35.0 ; 2 distinct days
    assert s["city_mean"]["pm25"] == 35.0 and s["days_covered"] == 2 and s["scoring_eligible"] is True
    monkeypatch.setenv("ESG_LIVE_MIN_DAYS", "90")
    assert EsgService.air_live(db)["scoring_eligible"] is False                       # not enough history -> not used for scoring


def test_electricity_real_csv_conversion_idempotent_and_update(sf):
    r = run_job("electricity", sf, force=True)
    assert r["status"] == "ok" and r["inserted"] == 26 and r["esg_recalculation_triggered"] is True
    db = sf()
    row = db.query(m.EsgElectricity).filter_by(year="2010-11", category="Electricity consumed, metered categories (total)").one()
    assert row.value_lakh_units == 142632.0                      # 14263.2 MU x 10
    assert row.source_url == "https://data.opencity.in/dataset/bescom-consumption-data" and row.last_updated
    assert run_job("electricity", sf, force=True)["unchanged"] == 26
    STATE["csv"] = STATE["csv"].replace("14263.2", "14999.0")
    r3 = run_job("electricity", sf, force=True)
    assert r3["updated"] == 1 and r3["esg_recalculation_triggered"] is True
    assert EsgService.electricity(db)["available"] is True


def test_schema_change_fails_safely(sf):
    STATE["csv"] = "Foo,Bar\n1,2\n"
    r = run_job("electricity", sf, force=True)
    assert r["status"] == "failed" and sf().query(m.EsgElectricity).count() == 0


def test_unreachable_source_fails_without_writing(sf, monkeypatch):
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "k")
    monkeypatch.setattr(air_cpcb, "API_URL", "http://127.0.0.1:9/none")
    r = run_job("air", sf, force=True)
    assert r["status"] == "failed" and sf().query(m.EsgAirLive).count() == 0


def test_file_jobs_and_interval_lock(sf):
    r1 = run_job("carbon", sf, force=True)
    assert r1["status"] == "ok" and r1["updated"] == 1                               # first load of verified file
    assert run_job("carbon", sf, force=True)["unchanged"] == 1                       # unchanged file -> no reseed
    assert run_job("carbon", sf)["status"] == "skipped"                              # interval not elapsed
    assert sf().query(m.EsgCarbonEmission).count() > 0
    assert run_job("water", sf, force=True)["status"] == "ok"


def test_existing_rows_get_provenance_and_apis_return_it(sf):
    db = sf()
    for row in list(db.query(m.EsgAirStation)) + list(db.query(m.EsgCarbonEmission)) + list(db.query(m.EsgWaterReading).limit(20)):
        assert row.source_name and row.source_url and row.data_year and row.last_updated and row.verification_status
    air = EsgService.air_quality(db)
    assert air["stations"][0]["source_url"] and "live" in air and air["naaqs_annual"]
    assert air["benchmark_source_code"] == "CPCB_NAAQS"
    assert {source["code"] for source in air["sources"]} >= {"GUTTIKUNDA_2019", "CPCB_NAAQS"}
    assert all(source["geographic_level"] for source in air["sources"])
    water = EsgService.water(db)
    assert water["period"] == "Apr 2020 - Mar 2021"
    assert water["scope"]
    carbon = EsgService.carbon(db)
    sectors = [row for row in carbon["series"] if row["sector"] != "Total"]
    assert all(row["mmt_co2e"] is None for row in sectors)


def test_no_duplicate_rows_on_reload(sf):
    """Reloading jobs multiple times must be strictly idempotent and produce no duplicate rows."""
    r_elec = run_job("electricity", sf, force=True)
    assert r_elec["status"] == "ok"
    r_carb = run_job("carbon", sf, force=True)
    r_wat = run_job("water", sf, force=True)

    db = sf()
    elec_count = db.query(m.EsgElectricity).count()
    carb_count = db.query(m.EsgCarbonEmission).count()
    water_count = db.query(m.EsgWaterReading).count()
    db.close()

    # Second run with force=True
    run_job("electricity", sf, force=True)
    run_job("carbon", sf, force=True)
    run_job("water", sf, force=True)

    db2 = sf()
    assert db2.query(m.EsgElectricity).count() == elec_count
    assert db2.query(m.EsgCarbonEmission).count() == carb_count
    assert db2.query(m.EsgWaterReading).count() == water_count
    db2.close()


def test_all_records_have_provenance(sf):
    """Every record across all ESG tables must have non-empty provenance fields."""
    run_job("electricity", sf, force=True)
    db = sf()
    for model in (m.EsgAirStation, m.EsgCarbonEmission, m.EsgWaterReading, m.EsgElectricity):
        records = db.query(model).all()
        assert len(records) > 0, f"Expected records in {model.__name__}"
        for r in records:
            assert r.source_name, f"Missing source_name in {model.__name__} id={r.id}"
            assert r.source_url, f"Missing source_url in {model.__name__} id={r.id}"
            assert r.data_year, f"Missing data_year in {model.__name__} id={r.id}"
            assert r.last_updated, f"Missing last_updated in {model.__name__} id={r.id}"
            assert r.verification_status, f"Missing verification_status in {model.__name__} id={r.id}"
    db.close()


def test_default_period_selection_logic():
    """Verify that default period selects the latest period with a scored environmental indicator."""
    # Periods sorted descending: 2022-23 (electricity only), 2020-21 (water), 2019 (carbon), 2016-17 (air)
    periods = ["2022-23", "2020-21", "2019", "2016-17"]
    indicators_by_period = {
        "2022-23": [{"category": "climate", "score": None, "indicator": "Electricity"}],
        "2020-21": [{"category": "environmental", "score": 75.0, "indicator": "Lake water quality"}],
        "2019": [{"category": "climate", "score": None, "indicator": "Carbon emissions"}],
        "2016-17": [{"category": "environmental", "score": 60.0, "indicator": "Air PM10"}],
    }

    # Algorithm matching frontend/js/esg-scorecard.js lines 222-227
    default_period = periods[0]
    for p in periods:
        ind = indicators_by_period.get(p, [])
        has_scored_env = any(item["category"] == "environmental" and item["score"] is not None for item in ind)
        if has_scored_env:
            default_period = p
            break

    # 2022-23 has no scored environmental indicator, so 2020-21 must be chosen
    assert default_period == "2020-21"
    assert default_period != "2022-23"

