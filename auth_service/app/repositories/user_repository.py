from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, User)

    async def get_by_email(self, email: str) -> User | None:
        result = await self.session.execute(
            select(User).where(func.lower(User.email) == email.lower())
        )
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        return (await self.get_by_email(email)) is not None

    async def list_users(
        self, offset: int = 0, limit: int = 20
    ) -> tuple[list[User], int]:
        total = (await self.session.execute(select(func.count()).select_from(User))).scalar_one()
        result = await self.session.execute(
            select(User).order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        return list(result.scalars().all()), total

    async def record_successful_login(self, user: User) -> None:
        user.failed_login_attempts = 0
        user.locked_until = None
        user.last_login_at = datetime.now(timezone.utc)
        await self.session.flush()

    async def record_failed_login(self, user: User) -> None:
        user.failed_login_attempts += 1
        await self.session.flush()

    async def lock_account(self, user: User, until: datetime) -> None:
        user.locked_until = until
        await self.session.flush()
