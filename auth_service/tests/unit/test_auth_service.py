"""
Unit tests for AuthService with repositories mocked out.

These exercise business rules (lockout thresholds, token rotation, reuse
detection) in isolation from any real database, so they run fast and
pinpoint logic bugs precisely.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.constants import UserRole
from app.core.security import create_refresh_token, hash_password
from app.exceptions.custom import (
    AccountLockedError,
    EmailAlreadyExistsError,
    InvalidCredentialsError,
    TokenRevokedError,
)
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.repositories.token_repository import hash_token
from app.services.auth_service import AuthService


def make_user(**overrides) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        email="user@example.com",
        hashed_password=hash_password("CorrectP@ss1"),
        role=UserRole.USER,
        is_active=True,
        failed_login_attempts=0,
        locked_until=None,
    )
    defaults.update(overrides)
    return User(**defaults)


@pytest.fixture
def user_repo():
    repo = MagicMock()
    repo.get_by_email = AsyncMock(return_value=None)
    repo.get_by_id = AsyncMock(return_value=None)
    repo.email_exists = AsyncMock(return_value=False)
    repo.add = AsyncMock(side_effect=lambda u: u)
    repo.commit = AsyncMock()
    repo.record_successful_login = AsyncMock()

    async def _record_failed_login(user):
        # Real repository mutates the persisted row's counter — mirror that
        # here so lockout-threshold logic can be exercised against the mock.
        user.failed_login_attempts += 1

    repo.record_failed_login = AsyncMock(side_effect=_record_failed_login)
    repo.lock_account = AsyncMock()
    return repo


@pytest.fixture
def token_repo():
    repo = MagicMock()
    repo.create = AsyncMock()
    repo.commit = AsyncMock()
    repo.get_by_jti = AsyncMock(return_value=None)
    repo.revoke = AsyncMock()
    repo.revoke_all_for_user = AsyncMock()
    repo.mark_rotated = AsyncMock()
    return repo


@pytest.fixture
def auth_service(user_repo, token_repo):
    return AuthService(user_repo, token_repo)


class TestRegister:
    async def test_register_creates_user_with_hashed_password(self, auth_service, user_repo):
        from app.schemas.user import UserCreate

        payload = UserCreate(email="new@example.com", password="Str0ng!Pass")
        user = await auth_service.register(payload)

        assert user.email == "new@example.com"
        assert user.hashed_password != "Str0ng!Pass"
        user_repo.commit.assert_awaited_once()

    async def test_register_rejects_duplicate_email(self, auth_service, user_repo):
        from app.schemas.user import UserCreate

        user_repo.email_exists = AsyncMock(return_value=True)
        payload = UserCreate(email="dupe@example.com", password="Str0ng!Pass")

        with pytest.raises(EmailAlreadyExistsError):
            await auth_service.register(payload)


class TestAuthenticate:
    async def test_authenticate_succeeds_with_correct_credentials(
        self, auth_service, user_repo, token_repo
    ):
        user = make_user()
        user_repo.get_by_email = AsyncMock(return_value=user)

        result = await auth_service.authenticate(user.email, "CorrectP@ss1")

        assert result.access_token
        assert result.refresh_token
        assert result.token_type == "bearer"
        user_repo.record_successful_login.assert_awaited_once_with(user)
        token_repo.create.assert_awaited_once()

    async def test_authenticate_fails_for_unknown_email(self, auth_service, user_repo):
        user_repo.get_by_email = AsyncMock(return_value=None)
        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate("ghost@example.com", "whatever")

    async def test_authenticate_fails_for_wrong_password(self, auth_service, user_repo):
        user = make_user()
        user_repo.get_by_email = AsyncMock(return_value=user)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate(user.email, "WrongPassword!")
        user_repo.record_failed_login.assert_awaited_once_with(user)

    async def test_account_locks_after_max_failed_attempts(self, auth_service, user_repo):
        from app.core.config import settings

        user = make_user(failed_login_attempts=settings.MAX_FAILED_LOGIN_ATTEMPTS - 1)
        user_repo.get_by_email = AsyncMock(return_value=user)

        with pytest.raises(InvalidCredentialsError):
            await auth_service.authenticate(user.email, "WrongPassword!")

        user_repo.lock_account.assert_awaited_once()

    async def test_authenticate_fails_when_account_locked(self, auth_service, user_repo):
        user = make_user(locked_until=datetime.now(timezone.utc) + timedelta(minutes=10))
        user_repo.get_by_email = AsyncMock(return_value=user)

        with pytest.raises(AccountLockedError):
            await auth_service.authenticate(user.email, "CorrectP@ss1")


class TestRefresh:
    async def test_refresh_reuse_of_revoked_token_revokes_whole_session_family(
        self, auth_service, token_repo
    ):
        raw_token, jti = create_refresh_token(subject=str(uuid.uuid4()))
        stored = RefreshToken(
            id=uuid.uuid4(),
            user_id=uuid.uuid4(),
            jti=jti,
            token_hash=hash_token(raw_token),
            revoked=True,  # already used once — this is a replay
            expires_at=datetime.now(timezone.utc) + timedelta(days=1),
        )
        token_repo.get_by_jti = AsyncMock(return_value=stored)

        with pytest.raises(TokenRevokedError):
            await auth_service.refresh(raw_token)

        token_repo.revoke_all_for_user.assert_awaited_once_with(stored.user_id)
