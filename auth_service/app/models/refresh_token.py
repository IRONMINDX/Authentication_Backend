import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.user import User


class RefreshToken(Base):
    """
    Server-side record of an issued refresh token.

    We never store the raw JWT — only a hash of it (`token_hash`) plus its
    `jti`. This lets us revoke individual sessions, support rotation, and
    detect reuse of a revoked token (a strong signal of theft) without
    being able to reconstruct the original token from the DB.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    jti: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False)

    revoked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # If this token was rotated, points at the jti of its replacement.
    replaced_by_jti: Mapped[str | None] = mapped_column(String(64), nullable=True)

    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="refresh_tokens")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<RefreshToken jti={self.jti} user_id={self.user_id} revoked={self.revoked}>"
