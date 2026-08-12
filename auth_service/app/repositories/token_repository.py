import hashlib
import uuid
from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.refresh_token import RefreshToken
from app.repositories.base import BaseRepository


def hash_token(raw_token: str) -> str:
    """
    Deterministic hash of the raw JWT for storage/lookup.

    We use SHA-256 (not bcrypt) here deliberately: refresh tokens are already
    high-entropy random-looking JWTs, so we need fast, deterministic lookup
    by hash rather than slow per-candidate verification.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


class TokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, session: AsyncSession):
        super().__init__(session, RefreshToken)

    async def get_by_jti(self, jti: str) -> RefreshToken | None:
        result = await self.session.execute(select(RefreshToken).where(RefreshToken.jti == jti))
        return result.scalar_one_or_none()

    async def create(
        self,
        user_id: uuid.UUID,
        jti: str,
        raw_token: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> RefreshToken:
        token = RefreshToken(
            user_id=user_id,
            jti=jti,
            token_hash=hash_token(raw_token),
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return await self.add(token)

    async def revoke(self, token: RefreshToken) -> None:
        token.revoked = True
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: uuid.UUID) -> None:
        await self.session.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked.is_(False))
            .values(revoked=True)
        )
        await self.session.flush()

    async def mark_rotated(self, token: RefreshToken, new_jti: str) -> None:
        token.revoked = True
        token.replaced_by_jti = new_jti
        await self.session.flush()
