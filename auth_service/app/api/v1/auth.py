from fastapi import APIRouter, Request, status

from app.core.config import settings
from app.dependencies.auth import CurrentUser
from app.dependencies.services import AuthServiceDep
from app.middleware.rate_limit import limiter
from app.schemas.auth import (
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    TokenResponse,
)
from app.schemas.user import PasswordChange, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _client_meta(request: Request) -> tuple[str | None, str | None]:
    return request.headers.get("user-agent"), (request.client.host if request.client else None)


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
async def register(request: Request, payload: UserCreate, auth_service: AuthServiceDep) -> UserRead:
    user = await auth_service.register(payload)
    return UserRead.model_validate(user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate with email and password, receive access/refresh tokens",
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request, payload: LoginRequest, auth_service: AuthServiceDep
) -> TokenResponse:
    user_agent, ip = _client_meta(request)
    return await auth_service.authenticate(payload.email, payload.password, user_agent, ip)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Exchange a valid refresh token for a new token pair",
)
async def refresh(
    request: Request, payload: RefreshRequest, auth_service: AuthServiceDep
) -> TokenResponse:
    user_agent, ip = _client_meta(request)
    return await auth_service.refresh(payload.refresh_token, user_agent, ip)


@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Revoke a single refresh token (log out of the current session)",
)
async def logout(payload: LogoutRequest, auth_service: AuthServiceDep) -> MessageResponse:
    await auth_service.logout(payload.refresh_token)
    return MessageResponse(message="Successfully logged out.")


@router.post(
    "/logout-all",
    response_model=MessageResponse,
    summary="Revoke all refresh tokens for the current user (log out everywhere)",
)
async def logout_all(current_user: CurrentUser, auth_service: AuthServiceDep) -> MessageResponse:
    await auth_service.logout_all_sessions(current_user.id)
    return MessageResponse(message="Successfully logged out of all sessions.")


@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Change the current user's password (invalidates all sessions)",
)
async def change_password(
    payload: PasswordChange, current_user: CurrentUser, auth_service: AuthServiceDep
) -> MessageResponse:
    await auth_service.change_password(
        current_user, payload.current_password, payload.new_password
    )
    return MessageResponse(message="Password updated successfully. Please log in again.")
