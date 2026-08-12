"""
Domain exceptions.

These carry no knowledge of HTTP — they represent business-rule failures.
The API layer (via exception handlers) translates them into HTTP responses.
This keeps services/repositories testable without spinning up FastAPI.
"""
from app.core.constants import ErrorCode


class AppException(Exception):
    """Base class for all domain exceptions."""

    status_code: int = 500
    error_code: ErrorCode = ErrorCode.INTERNAL_ERROR
    message: str = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.message
        super().__init__(self.message)


class InvalidCredentialsError(AppException):
    status_code = 401
    error_code = ErrorCode.INVALID_CREDENTIALS
    message = "Incorrect email or password."


class EmailAlreadyExistsError(AppException):
    status_code = 409
    error_code = ErrorCode.EMAIL_ALREADY_EXISTS
    message = "An account with this email already exists."


class UserNotFoundError(AppException):
    status_code = 404
    error_code = ErrorCode.USER_NOT_FOUND
    message = "User not found."


class InactiveUserError(AppException):
    status_code = 403
    error_code = ErrorCode.INACTIVE_USER
    message = "This account has been deactivated."


class AccountLockedError(AppException):
    status_code = 423
    error_code = ErrorCode.ACCOUNT_LOCKED
    message = "Account temporarily locked due to too many failed login attempts."


class InvalidTokenError(AppException):
    status_code = 401
    error_code = ErrorCode.INVALID_TOKEN
    message = "Invalid or malformed token."


class ExpiredTokenError(AppException):
    status_code = 401
    error_code = ErrorCode.EXPIRED_TOKEN
    message = "Token has expired."


class TokenRevokedError(AppException):
    status_code = 401
    error_code = ErrorCode.TOKEN_REVOKED
    message = "Token has been revoked."


class WeakPasswordError(AppException):
    status_code = 422
    error_code = ErrorCode.WEAK_PASSWORD
    message = "Password does not meet complexity requirements."


class SamePasswordError(AppException):
    status_code = 422
    error_code = ErrorCode.SAME_PASSWORD
    message = "New password must be different from the current password."


class PermissionDeniedError(AppException):
    status_code = 403
    error_code = ErrorCode.PERMISSION_DENIED
    message = "You do not have permission to perform this action."
