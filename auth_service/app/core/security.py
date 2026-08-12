"""
Security primitives: password hashing and JWT creation/verification.

Kept framework-agnostic (no FastAPI imports) so it can be unit tested in
isolation and reused outside the web layer if needed.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import settings
from app.core.constants import TokenType

# We call the `bcrypt` library directly rather than going through passlib's
# CryptContext. passlib 1.7.x is unmaintained and its bcrypt backend is
# incompatible with bcrypt>=4.1 (it probes a removed `__about__` attribute
# and mishandles bcrypt's 72-byte input limit). Calling bcrypt directly is
# simpler and avoids that dependency-compatibility trap.
_BCRYPT_MAX_BYTES = 72


def hash_password(plain_password: str) -> str:
    """Hash a plaintext password using bcrypt (default cost factor: 12)."""
    password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    hashed = bcrypt.hashpw(password_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    password_bytes = plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES]
    try:
        return bcrypt.checkpw(password_bytes, hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed/foreign hash format.
        return False


# ---------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------
class TokenPayload:
    """Typed wrapper around a decoded JWT payload."""

    def __init__(self, data: dict[str, Any]):
        self.sub: str = data["sub"]
        self.jti: str = data["jti"]
        self.type: str = data["type"]
        self.exp: int = data["exp"]
        self.iat: int = data["iat"]
        self.role: str | None = data.get("role")


def _create_token(
    subject: str,
    token_type: TokenType,
    expires_delta: timedelta,
    extra_claims: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Create a signed JWT. Returns (token, jti)."""
    now = datetime.now(timezone.utc)
    jti = str(uuid.uuid4())
    payload: dict[str, Any] = {
        "sub": subject,
        "jti": jti,
        "type": token_type.value,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti


def create_access_token(subject: str, role: str | None = None) -> tuple[str, str]:
    return _create_token(
        subject=subject,
        token_type=TokenType.ACCESS,
        expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        extra_claims={"role": role} if role else None,
    )


def create_refresh_token(subject: str) -> tuple[str, str]:
    return _create_token(
        subject=subject,
        token_type=TokenType.REFRESH,
        expires_delta=timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> TokenPayload:
    """
    Decode and validate a JWT's signature/expiry.

    Raises `jose.JWTError` (or a subclass) on any failure — callers should
    catch this and translate it into the appropriate domain exception.
    """
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    return TokenPayload(payload)


def is_token_error(exc: Exception) -> bool:
    return isinstance(exc, JWTError)
