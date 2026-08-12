import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.core.config import settings
from app.core.constants import UserRole


def validate_password_strength(password: str) -> str:
    """Shared password-policy validator used by registration & password change."""
    if len(password) < settings.PASSWORD_MIN_LENGTH:
        raise ValueError(
            f"Password must be at least {settings.PASSWORD_MIN_LENGTH} characters long."
        )
    if settings.PASSWORD_REQUIRE_UPPERCASE and not re.search(r"[A-Z]", password):
        raise ValueError("Password must contain at least one uppercase letter.")
    if settings.PASSWORD_REQUIRE_LOWERCASE and not re.search(r"[a-z]", password):
        raise ValueError("Password must contain at least one lowercase letter.")
    if settings.PASSWORD_REQUIRE_DIGIT and not re.search(r"\d", password):
        raise ValueError("Password must contain at least one digit.")
    if settings.PASSWORD_REQUIRE_SPECIAL and not re.search(r"[^\w\s]", password):
        raise ValueError("Password must contain at least one special character.")
    return password


class UserBase(BaseModel):
    email: EmailStr
    full_name: str | None = Field(default=None, max_length=255)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=128)

    @field_validator("password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        return validate_password_strength(v)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime
    last_login_at: datetime | None = None


class UserInDB(UserRead):
    """Internal representation including the password hash — never returned by the API."""

    hashed_password: str


class PasswordChange(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def check_password_strength(cls, v: str) -> str:
        return validate_password_strength(v)
