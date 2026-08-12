"""FastAPI dependencies for extracting/validating the authenticated user."""
import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.constants import TokenType, UserRole
from app.core.security import decode_token
from app.dependencies.services import UserRepo
from app.exceptions.custom import (
    InactiveUserError,
    InvalidTokenError,
    PermissionDeniedError,
    UserNotFoundError,
)
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=True, description="JWT access token")


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer_scheme)],
    user_repo: UserRepo,
) -> User:
    token = credentials.credentials
    try:
        payload = decode_token(token)
    except Exception as exc:
        raise InvalidTokenError() from exc

    if payload.type != TokenType.ACCESS.value:
        raise InvalidTokenError("Provided token is not an access token.")

    try:
        user_id = uuid.UUID(payload.sub)
    except ValueError as exc:
        raise InvalidTokenError() from exc

    user = await user_repo.get_by_id(user_id)
    if user is None:
        raise UserNotFoundError()
    if not user.is_active:
        raise InactiveUserError()

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_active_verified_user(current_user: CurrentUser) -> User:
    return current_user


def require_role(*allowed_roles: UserRole):
    """Dependency factory for RBAC: `Depends(require_role(UserRole.ADMIN))`."""

    async def _checker(current_user: CurrentUser) -> User:
        if current_user.role not in allowed_roles:
            raise PermissionDeniedError()
        return current_user

    return _checker


RequireAdmin = Annotated[User, Depends(require_role(UserRole.ADMIN))]
