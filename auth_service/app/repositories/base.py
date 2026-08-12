"""Generic repository providing common CRUD operations over a SQLAlchemy model."""
import uuid
from typing import Generic, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    def __init__(self, session: AsyncSession, model: type[ModelType]):
        self.session = session
        self.model = model

    async def get_by_id(self, id_: uuid.UUID) -> ModelType | None:
        result = await self.session.execute(select(self.model).where(self.model.id == id_))
        return result.scalar_one_or_none()

    async def add(self, instance: ModelType) -> ModelType:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def delete(self, instance: ModelType) -> None:
        await self.session.delete(instance)
        await self.session.flush()

    async def commit(self) -> None:
        await self.session.commit()
