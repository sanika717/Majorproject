from sqlalchemy import Column, Integer, BigInteger, Float, String, Text, JSON
from backend.app.db.session import Base

class ConstructionWorkOrder(Base):
    __tablename__ = "construction_work_orders"

    id = Column(Integer, primary_key=True, index=True)
    slno = Column(Integer, index=True)
    work_order_id = Column(String(50), index=True)
    ward = Column(String(50), index=True, nullable=False)
    wodetails = Column(Text, nullable=False)
    contractor = Column(String(255), index=True, nullable=True)
    brnumber = Column(String(255), nullable=True)
    amount = Column(BigInteger, nullable=False)
    nett = Column(BigInteger, nullable=False)
    deduction = Column(BigInteger, nullable=False)


class ConstructionWardSummary(Base):
    __tablename__ = "construction_ward_summaries"

    id = Column(Integer, primary_key=True, index=True)
    ward = Column(String(50), unique=True, index=True, nullable=False)
    total_work_orders = Column(Integer, nullable=False)
    total_amount = Column(BigInteger, nullable=False)
    avg_project_amount = Column(Float, nullable=False)
    total_net_expenditure = Column(BigInteger, nullable=False)
    avg_net_amount = Column(Float, nullable=False)
    total_deduction = Column(BigInteger, nullable=False)
    avg_deduction = Column(Float, nullable=False)
    unique_contractors = Column(Integer, nullable=False)
    drain_projects = Column(Integer, default=0)
    road_projects = Column(Integer, default=0)
    maintenance_projects = Column(Integer, default=0)
    development_projects = Column(Integer, default=0)
    water_projects = Column(Integer, default=0)
    cluster = Column(Integer, index=True)
    cluster_name = Column(String(100))


class ConstructionClusterStat(Base):
    __tablename__ = "construction_cluster_stats"

    id = Column(Integer, primary_key=True, index=True)
    cluster = Column(Integer, unique=True, nullable=False)
    cluster_name = Column(String(100), nullable=False)
    ward_count = Column(Integer, nullable=False)
    avg_work_orders = Column(Float, nullable=False)
    avg_total_amount = Column(Float, nullable=False)
    avg_net_expenditure = Column(Float, nullable=False)
    avg_deduction = Column(Float, nullable=False)
    avg_contractors = Column(Float, nullable=False)


class ConstructionMeta(Base):
    __tablename__ = "construction_metadata"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(JSON, nullable=False)
