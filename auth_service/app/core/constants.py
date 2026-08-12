"""Shared enums and constant values."""
import enum


class UserRole(str, enum.Enum):
    USER = "user"
    ADMIN = "admin"


class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"


class ErrorCode(str, enum.Enum):
    """Machine-readable error codes returned in API error responses."""

    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    EMAIL_ALREADY_EXISTS = "EMAIL_ALREADY_EXISTS"
    USER_NOT_FOUND = "USER_NOT_FOUND"
    INACTIVE_USER = "INACTIVE_USER"
    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    INVALID_TOKEN = "INVALID_TOKEN"
    EXPIRED_TOKEN = "EXPIRED_TOKEN"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    WEAK_PASSWORD = "WEAK_PASSWORD"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SAME_PASSWORD = "SAME_PASSWORD"
