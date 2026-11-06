"""
UrbanPulse Repositories Module.
Encapsulates database access operations using the Repository Pattern.
"""

from backend.app.repositories.base import BaseRepository
from backend.app.repositories.construction_repo import ConstructionRepository
from backend.app.repositories.crime_repo import CrimeRepository
from backend.app.repositories.complaint_repo import ComplaintRepository
from backend.app.repositories.esg_repo import EsgRepository

__all__ = [
    "BaseRepository",
    "ConstructionRepository",
    "CrimeRepository",
    "ComplaintRepository",
    "EsgRepository",
]
