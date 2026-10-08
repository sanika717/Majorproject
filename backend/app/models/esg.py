from sqlalchemy import Column, Integer, Float, String, Boolean, Text, DateTime, UniqueConstraint
from backend.app.db.session import Base


class ProvenanceMixin:
    """Per-record provenance required for every ESG data row (added in the auto-update phase).
    Existing databases get these columns via services/esg_update/provenance.ensure_columns()."""
    source_name = Column(String(300), nullable=True)
    source_url = Column(Text, nullable=True)
    data_year = Column(String(80), nullable=True)          # year/period the SOURCE data refers to
    last_updated = Column(DateTime, nullable=True)         # when this row was last written/confirmed by us
    verification_status = Column(String(40), nullable=True)


class EsgSource(Base):
    __tablename__ = "esg_sources"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(60), unique=True, index=True, nullable=False)
    title = Column(Text, nullable=False)
    publisher = Column(String(300), nullable=True)
    url = Column(Text, nullable=True)
    doi = Column(Text, nullable=True)
    period = Column(String(60), nullable=True)
    location = Column(String(300), nullable=True)
    geographic_level = Column(String(300), nullable=True)
    note = Column(Text, nullable=True)


class EsgAirStation(ProvenanceMixin, Base):
    __tablename__ = "esg_air_stations"
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(20), unique=True, index=True, nullable=False)
    name = Column(String(200), nullable=False)
    category = Column(String(20), nullable=True)
    year = Column(String(20), nullable=False)
    latitude = Column(Float, nullable=True)   # approximate locality centre; NULL = not mapped
    longitude = Column(Float, nullable=True)
    so2 = Column(Float, nullable=True)
    no2 = Column(Float, nullable=True)
    pm10 = Column(Float, nullable=True)
    pm25 = Column(Float, nullable=True)
    nh3 = Column(Float, nullable=True)
    lead = Column(Float, nullable=True)
    co = Column(Float, nullable=True)
    aqi = Column(Float, nullable=True)        # NULL until a genuine CPCB/KSPCB AQI value is imported
    source_code = Column(String(60), nullable=False)


class EsgCarbonEmission(ProvenanceMixin, Base):
    __tablename__ = "esg_carbon_emissions"
    id = Column(Integer, primary_key=True, index=True)
    year = Column(Integer, index=True, nullable=False)
    sector = Column(String(200), nullable=False)
    mmt_co2e = Column(Float, nullable=True)
    share_pct = Column(Float, nullable=True)
    is_derived = Column(Boolean, default=False)
    boundary = Column(String(100), nullable=True)
    source_code = Column(String(60), nullable=False)


class EsgWaterReading(ProvenanceMixin, Base):
    __tablename__ = "esg_water_readings"
    id = Column(Integer, primary_key=True, index=True)
    station_code = Column(String(20), index=True, nullable=False)
    station_name = Column(String(200), nullable=False)
    district = Column(String(200), nullable=True)
    region = Column(String(50), index=True, nullable=True)
    month = Column(String(10), nullable=False)
    wq_class = Column(String(2), nullable=True)      # CPCB designated-use class A-E; NULL = not monitored
    wqi_status = Column(String(2), nullable=True)    # S / US
    source_code = Column(String(60), nullable=False)


class EsgElectricity(ProvenanceMixin, Base):
    __tablename__ = "esg_electricity"
    id = Column(Integer, primary_key=True, index=True)
    area = Column(String(200), nullable=False)
    category = Column(String(100), nullable=True)
    year = Column(String(20), nullable=False)
    value_lakh_units = Column(Float, nullable=False)
    source_code = Column(String(60), nullable=False)


class EsgAirLive(ProvenanceMixin, Base):
    """Station-level Bengaluru readings from the CPCB real-time AQI feed (data.gov.in). Append-only history."""
    __tablename__ = "esg_air_live"
    id = Column(Integer, primary_key=True, index=True)
    station = Column(String(300), index=True, nullable=False)
    city = Column(String(100), nullable=True)
    state = Column(String(100), nullable=True)
    latitude = Column(Float, nullable=True)     # only if the source supplies it
    longitude = Column(Float, nullable=True)
    pollutant_id = Column(String(30), index=True, nullable=False)
    pollutant_min = Column(Float, nullable=True)
    pollutant_avg = Column(Float, nullable=True)
    pollutant_max = Column(Float, nullable=True)
    observed_at = Column(DateTime, index=True, nullable=False)   # the source's own last_update (IST as published)
    __table_args__ = (UniqueConstraint("station", "pollutant_id", "observed_at", name="uq_esg_air_live"),)


class EsgUpdateRun(Base):
    """One row per updater job execution (also acts as the cross-worker lock)."""
    __tablename__ = "esg_update_runs"
    id = Column(Integer, primary_key=True, index=True)
    job = Column(String(30), index=True, nullable=False)        # air | electricity | carbon | water
    started_at = Column(DateTime, nullable=False)
    finished_at = Column(DateTime, nullable=True)
    status = Column(String(20), nullable=False)                 # running | ok | failed | skipped
    fetched = Column(Integer, default=0)
    inserted = Column(Integer, default=0)
    updated = Column(Integer, default=0)
    unchanged = Column(Integer, default=0)
    data_hash = Column(String(64), nullable=True)               # file-watch jobs: hash of the verified files
    source_url = Column(Text, nullable=True)
    message = Column(Text, nullable=True)


class EsgRecalcLog(Base):
    """Written each time the verified inputs of the ESG score change (scores are recomputed on next read)."""
    __tablename__ = "esg_recalc_log"
    id = Column(Integer, primary_key=True, index=True)
    triggered_at = Column(DateTime, nullable=False)
    data_version = Column(String(64), nullable=False)
    previous_version = Column(String(64), nullable=True)
    reason = Column(Text, nullable=True)
