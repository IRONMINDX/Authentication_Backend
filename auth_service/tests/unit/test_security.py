"""Unit tests for app.core.security — pure functions, no DB/HTTP involved."""
import time

import pytest
from jose import JWTError

from app.core.constants import TokenType
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


class TestPasswordHashing:
    def test_hash_password_returns_different_value_than_plaintext(self):
        hashed = hash_password("MyS3cret!")
        assert hashed != "MyS3cret!"

    def test_verify_password_succeeds_for_correct_password(self):
        hashed = hash_password("MyS3cret!")
        assert verify_password("MyS3cret!", hashed) is True

    def test_verify_password_fails_for_incorrect_password(self):
        hashed = hash_password("MyS3cret!")
        assert verify_password("WrongPassword!", hashed) is False

    def test_same_password_hashed_twice_produces_different_hashes(self):
        # bcrypt uses a random salt per hash — this guards against a
        # regression where salting is accidentally disabled.
        h1 = hash_password("SamePassword1!")
        h2 = hash_password("SamePassword1!")
        assert h1 != h2
        assert verify_password("SamePassword1!", h1)
        assert verify_password("SamePassword1!", h2)


class TestJWT:
    def test_create_and_decode_access_token(self):
        token, jti = create_access_token(subject="user-123", role="user")
        payload = decode_token(token)

        assert payload.sub == "user-123"
        assert payload.type == TokenType.ACCESS.value
        assert payload.jti == jti
        assert payload.role == "user"

    def test_create_and_decode_refresh_token(self):
        token, jti = create_refresh_token(subject="user-123")
        payload = decode_token(token)

        assert payload.sub == "user-123"
        assert payload.type == TokenType.REFRESH.value
        assert payload.jti == jti

    def test_each_token_has_unique_jti(self):
        _, jti1 = create_access_token(subject="user-123")
        _, jti2 = create_access_token(subject="user-123")
        assert jti1 != jti2

    def test_decode_invalid_token_raises(self):
        with pytest.raises(JWTError):
            decode_token("not.a.valid.token")

    def test_decode_tampered_token_raises(self):
        token, _ = create_access_token(subject="user-123")
        tampered = token[:-4] + "abcd"
        with pytest.raises(JWTError):
            decode_token(tampered)
