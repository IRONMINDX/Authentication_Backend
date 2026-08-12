"""
Shared pytest fixtures.

Tests run against an in-memory SQLite database (via aiosqlite) rather than
Postgres, so the suite is fast and has zero external dependencies in CI.
The app's repositories/services use only portable SQLAlchemy constructs,
so behavior parity with Postgres is preserved; anything Postgres-specific
(e.g. exact native column types) is covered separately by the Alembic
migration itself, which targets Postgres in production.

Environment variables are set *before* importing anything from `app`,
since `app.core.config.settings` is instantiated at import time.
"""
import os

os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite://")  # in-memory
os.environ.setdefault("SECRET_KEY", "test-secret-key-do-not-use-in-production")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "15")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_DAYS", "30")
os.environ.setdefault("MAX_FAILED_LOGIN_ATTEMPTS", "5")
os.environ.setdefault("ACCOUNT_LOCKOUT_MINUTES", "15")

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.db.base_all_models import Base
from app.db.session import get_db
from app.main import create_app
from app.models.user import User
from app.core.constants import UserRole
from app.core.security import hash_password


@pytest_asyncio.fixture
async def db_engine():
    """A fresh in-memory SQLite engine per test, using StaticPool so the
    same in-memory DB is shared across connections within the test."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def app(db_engine):
    """FastAPI app instance with the DB dependency overridden to use the
    isolated test engine, so every request in a test hits the same DB."""
    test_app = create_app()
    session_factory = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async def _get_test_db():
        async with session_factory() as session:
            try:
                yield session
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    test_app.dependency_overrides[get_db] = _get_test_db
    return test_app


@pytest_asyncio.fixture
async def client(app) -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest_asyncio.fixture
async def existing_user(db_session: AsyncSession) -> User:
    user = User(
        email="existing@example.com",
        hashed_password=hash_password("StrongP@ss1"),
        full_name="Existing User",
        role=UserRole.USER,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        email="admin@example.com",
        hashed_password=hash_password("AdminP@ss1"),
        full_name="Admin User",
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user
