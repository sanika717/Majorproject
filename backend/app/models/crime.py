from sqlalchemy import Column, Integer, Float, String, JSON
from backend.app.db.session import Base

class CrimeHistorical(Base):
    __tablename__ = "crime_historical"

    id = Column(Integer, primary_key=True, index=True)
    period_label = Column(String(100), nullable=False)
    total_crimes = Column(Integer, nullable=False)
    fatal_crimes = Column(Integer, nullable=False)
    non_fatal_crimes = Column(Integer, nullable=False)
    fatal_percentage = Column(Float, nullable=False)
    highest_risk_year = Column(Integer, nullable=False)
    highest_risk_score = Column(Float, nullable=False)
    highest_risk_level = Column(String(50), nullable=False)
    highest_risk_volume_score = Column(Float, nullable=False)
    highest_risk_severity_score = Column(Float, nullable=False)
    volume_weight = Column(Float, default=0.60)
    severity_weight = Column(Float, default=0.40)


class CrimeRecord(Base):
    __tablename__ = "crime_records"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), index=True, nullable=False) # e.g. women, children, cyber, suicides, accidental
    year = Column(String(10), index=True, nullable=False)     # e.g. 2021, 2022, 2023
    item_name = Column(String(200), nullable=False)          # crime type, division name, or cause
    reported = Column(Integer, nullable=True)
    detected = Column(Integer, nullable=True)
    detection_pct = Column(Float, nullable=True)
    male = Column(Integer, nullable=True)
    female = Column(Integer, nullable=True)
    total = Column(Integer, nullable=True)
    extra_data = Column(JSON, nullable=True)


class CrimeCategoryYearSummary(Base):
    __tablename__ = "crime_category_year_summaries"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), index=True, nullable=False)
    year = Column(String(10), index=True, nullable=False)
    total_reported = Column(Integer, nullable=True)
    total_detected = Column(Integer, nullable=True)
    overall_detection_pct = Column(Float, nullable=True)
    total_suicides = Column(Integer, nullable=True)
    total_accidental_deaths = Column(Integer, nullable=True)
    total_male = Column(Integer, nullable=True)
    total_female = Column(Integer, nullable=True)


class CrimeMeta(Base):
    __tablename__ = "crime_metadata"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(JSON, nullable=False)
