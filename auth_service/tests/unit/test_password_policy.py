import pytest
from pydantic import ValidationError

from app.schemas.user import UserCreate


VALID_PASSWORD = "Str0ng!Pass"


class TestPasswordPolicy:
    def test_valid_password_accepted(self):
        user = UserCreate(email="a@example.com", password=VALID_PASSWORD)
        assert user.password == VALID_PASSWORD

    @pytest.mark.parametrize(
        "password,reason",
        [
            ("Sh0rt!", "too short"),
            ("alllowercase1!", "no uppercase"),
            ("ALLUPPERCASE1!", "no lowercase"),
            ("NoDigitsHere!", "no digit"),
            ("NoSpecialChar1", "no special character"),
        ],
    )
    def test_weak_passwords_rejected(self, password, reason):
        with pytest.raises(ValidationError):
            UserCreate(email="a@example.com", password=password)

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            UserCreate(email="not-an-email", password=VALID_PASSWORD)
