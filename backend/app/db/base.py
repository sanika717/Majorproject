from backend.app.db.session import Base
# Import all models here so that Alembic/Base.metadata can see them
from backend.app.models.user import User, UserRole
from backend.app.models.construction import (
    ConstructionWorkOrder,
    ConstructionWardSummary,
    ConstructionClusterStat,
    ConstructionMeta,
)
from backend.app.models.crime import (
    CrimeHistorical,
    CrimeRecord,
    CrimeCategoryYearSummary,
    CrimeMeta,
)
from backend.app.models.police import PoliceLocation
