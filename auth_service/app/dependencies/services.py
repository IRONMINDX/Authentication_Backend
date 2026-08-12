"""
Dependency-injection wiring.

Each `get_*` function is a FastAPI dependency that constructs a
repository/service bound to the current request's DB session. Keeping this
wiring in one place means swapping an implementation (e.g. a different
repository) only requires a change here, not in every route.
"""
from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.repositories.token_repository import TokenRepository
from app.repositories.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.user_service import UserService

DbSession = Annotated[AsyncSession, Depends(get_db)]


def get_user_repository(db: DbSession) -> UserRepository:
    return UserRepository(db)


def get_token_repository(db: DbSession) -> TokenRepository:
    return TokenRepository(db)


UserRepo = Annotated[UserRepository, Depends(get_user_repository)]
TokenRepo = Annotated[TokenRepository, Depends(get_token_repository)]


def get_auth_service(user_repo: UserRepo, token_repo: TokenRepo) -> AuthService:
    return AuthService(user_repo, token_repo)


def get_user_service(user_repo: UserRepo) -> UserService:
    return UserService(user_repo)


AuthServiceDep = Annotated[AuthService, Depends(get_auth_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
