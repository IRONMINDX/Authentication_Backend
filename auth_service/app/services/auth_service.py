"""
AuthService encapsulates all authentication business logic.

It depends only on repositories (data access) and core utilities (hashing,
JWT) — never on FastAPI request/response objects — so it can be unit tested
with mocked repositories and reused by non-HTTP entry points (CLI, workers).
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.constants import TokenType, UserRole
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.exceptions.custom import (
    AccountLockedError,
    EmailAlreadyExistsError,
    InactiveUserError,
    InvalidCredentialsError,
    InvalidTokenError,
    SamePasswordError,
    TokenRevokedError,
    UserNotFoundError,
)
from app.models.user import User
from app.repositories.token_repository import TokenRepository, hash_token
from app.repositories.user_repository import UserRepository
from app.schemas.auth import TokenResponse
from app.schemas.user import UserCreate


class AuthService:
    def __init__(self, user_repo: UserRepository, token_repo: TokenRepository):
        self.user_repo = user_repo
        self.token_repo = token_repo

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------
    async def register(self, data: UserCreate) -> User:
        if await self.user_repo.email_exists(data.email):
            raise EmailAlreadyExistsError()

        user = User(
            email=data.email.lower(),
            hashed_password=hash_password(data.password),
            full_name=data.full_name,
            role=UserRole.USER,
        )
        user = await self.user_repo.add(user)
        await self.user_repo.commit()
        return user

    # ------------------------------------------------------------------
    # Login
    # ------------------------------------------------------------------
    async def authenticate(
        self, email: str, password: str, user_agent: str | None = None, ip_address: str | None = None
    ) -> TokenResponse:
        user = await self.user_repo.get_by_email(email)
        if user is None:
            # Constant-shape response to avoid user enumeration via timing/behavior.
            raise InvalidCredentialsError()

        self._ensure_not_locked(user)

        if not verify_password(password, user.hashed_password):
            await self._handle_failed_login(user)
            raise InvalidCredentialsError()

        if not user.is_active:
            raise InactiveUserError()

        await self.user_repo.record_successful_login(user)
        await self.user_repo.commit()

        return await self._issue_token_pair(user, user_agent, ip_address)

    def _ensure_not_locked(self, user: User) -> None:
        locked_until = user.locked_until
        if locked_until is None:
            return
        if locked_until.tzinfo is None:
            locked_until = locked_until.replace(tzinfo=timezone.utc)
        if locked_until > datetime.now(timezone.utc):
            raise AccountLockedError()

    async def _handle_failed_login(self, user: User) -> None:
        await self.user_repo.record_failed_login(user)
        if user.failed_login_attempts >= settings.MAX_FAILED_LOGIN_ATTEMPTS:
            lock_until = datetime.now(timezone.utc) + timedelta(
                minutes=settings.ACCOUNT_LOCKOUT_MINUTES
            )
            await self.user_repo.lock_account(user, lock_until)
        await self.user_repo.commit()

    # ------------------------------------------------------------------
    # Token issuance / refresh / revocation
    # ------------------------------------------------------------------
    async def _issue_token_pair(
        self, user: User, user_agent: str | None = None, ip_address: str | None = None
    ) -> TokenResponse:
        access_token, _ = create_access_token(subject=str(user.id), role=user.role.value)
        refresh_token, jti = create_refresh_token(subject=str(user.id))

        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.REFRESH_TOKEN_EXPIRE_DAYS
        )
        await self.token_repo.create(
            user_id=user.id,
            jti=jti,
            raw_token=refresh_token,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await self.token_repo.commit()

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(
        self, raw_refresh_token: str, user_agent: str | None = None, ip_address: str | None = None
    ) -> TokenResponse:
        try:
            payload = decode_token(raw_refresh_token)
        except Exception as exc:  # jose.JWTError and subclasses
            raise InvalidTokenError() from exc

        if payload.type != TokenType.REFRESH.value:
            raise InvalidTokenError("Provided token is not a refresh token.")

        stored = await self.token_repo.get_by_jti(payload.jti)
        if stored is None:
            raise InvalidTokenError()

        if stored.token_hash != hash_token(raw_refresh_token):
            # jti matches but hash doesn't — should never happen unless tampered.
            raise InvalidTokenError()

        if stored.revoked:
            # Reuse of a revoked/rotated token: possible theft. Revoke the whole
            # session family for safety.
            await self.token_repo.revoke_all_for_user(stored.user_id)
            await self.token_repo.commit()
            raise TokenRevokedError()

        expires_at = stored.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise InvalidTokenError("Refresh token has expired.")

        user = await self.user_repo.get_by_id(stored.user_id)
        if user is None:
            raise UserNotFoundError()
        if not user.is_active:
            raise InactiveUserError()

        if settings.REFRESH_TOKEN_ROTATE:
            new_tokens = await self._issue_token_pair(user, user_agent, ip_address)
            new_payload = decode_token(new_tokens.refresh_token)
            await self.token_repo.mark_rotated(stored, new_payload.jti)
            await self.token_repo.commit()
            return new_tokens

        # Non-rotating mode: just issue a fresh access token, keep refresh token.
        access_token, _ = create_access_token(subject=str(user.id), role=user.role.value)
        return TokenResponse(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, raw_refresh_token: str) -> None:
        try:
            payload = decode_token(raw_refresh_token)
        except Exception as exc:
            raise InvalidTokenError() from exc

        stored = await self.token_repo.get_by_jti(payload.jti)
        if stored is not None and not stored.revoked:
            await self.token_repo.revoke(stored)
            await self.token_repo.commit()

    async def logout_all_sessions(self, user_id: uuid.UUID) -> None:
        await self.token_repo.revoke_all_for_user(user_id)
        await self.token_repo.commit()

    # ------------------------------------------------------------------
    # Password management
    # ------------------------------------------------------------------
    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise InvalidCredentialsError("Current password is incorrect.")
        if verify_password(new_password, user.hashed_password):
            raise SamePasswordError()

        user.hashed_password = hash_password(new_password)
        await self.user_repo.commit()
        # Invalidate all existing sessions after a password change.
        await self.token_repo.revoke_all_for_user(user.id)
        await self.token_repo.commit()
