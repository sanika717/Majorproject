"""
Base Repository Interface for UrbanPulse Data Access.
Implements the Repository Pattern to decouple business services from database operations.
"""

from typing import Generic, TypeVar, Type, List, Optional, Any
from sqlalchemy.orm import Session

T = TypeVar("T")


class BaseRepository(Generic[T]):
    """Generic repository providing standardized database CRUD operations."""

    def __init__(self, model_class: Type[T], db: Session):
        self.model_class = model_class
        self.db = db

    def get_by_id(self, id_val: Any) -> Optional[T]:
        return self.db.query(self.model_class).get(id_val)

    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        return self.db.query(self.model_class).offset(offset).limit(limit).all()

    def count(self) -> int:
        return self.db.query(self.model_class).count()

    def add(self, entity: T) -> T:
        self.db.add(entity)
        self.db.flush()
        return entity

    def delete(self, entity: T) -> None:
        self.db.delete(entity)
        self.db.flush()
