"""Async SQLAlchemy engine + sessionmaker, built from settings."""
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

_engine_kwargs = dict(echo=settings.DATABASE_ECHO, future=True, pool_pre_ping=True)

# SQLite (used in tests) doesn't support pool_size/max_overflow.
if not settings.DATABASE_URL.startswith("sqlite"):
    _engine_kwargs.update(
        pool_size=settings.DB_POOL_SIZE,
        max_overflow=settings.DB_MAX_OVERFLOW,
        pool_timeout=settings.DB_POOL_TIMEOUT,
    )

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)
