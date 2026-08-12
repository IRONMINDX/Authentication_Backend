import uuid

from app.exceptions.custom import PermissionDeniedError, UserNotFoundError
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.user import UserUpdate


class UserService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def get_by_id(self, user_id: uuid.UUID) -> User:
        user = await self.user_repo.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError()
        return user

    async def update_profile(self, user: User, data: UserUpdate) -> User:
        if data.full_name is not None:
            user.full_name = data.full_name
        await self.user_repo.commit()
        return user

    async def list_users(self, offset: int, limit: int) -> tuple[list[User], int]:
        return await self.user_repo.list_users(offset=offset, limit=limit)

    async def deactivate_user(self, actor: User, target_user_id: uuid.UUID) -> User:
        """Admin-only: deactivate another user's account."""
        from app.core.constants import UserRole  # local import avoids cycle at module load

        if actor.role != UserRole.ADMIN:
            raise PermissionDeniedError()

        target = await self.get_by_id(target_user_id)
        target.is_active = False
        await self.user_repo.commit()
        return target
