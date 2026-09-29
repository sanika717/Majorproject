from sqlalchemy import Column, Integer, Float, String
from backend.app.db.session import Base

class PoliceLocation(Base):
    __tablename__ = "police_locations"

    id = Column(Integer, primary_key=True, index=True)
    location_code = Column(String(50), unique=True, index=True, nullable=False) # e.g. ps-001
    name = Column(String(200), nullable=False)
    display_name = Column(String(255), nullable=False)
    category = Column(String(100), index=True, nullable=False) # e.g. Police Station, Railway Police Station, Police Outpost
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    icon = Column(String(50), nullable=True)
    source = Column(String(200), nullable=True)
