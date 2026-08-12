"""
Integration tests: exercise real HTTP requests against the FastAPI app,
backed by an isolated in-memory SQLite DB (see tests/conftest.py).
"""
import pytest


VALID_PASSWORD = "Str0ng!Pass1"


class TestRegister:
    async def test_register_returns_201_and_user_payload(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": VALID_PASSWORD, "full_name": "New User"},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["email"] == "new@example.com"
        assert "password" not in body
        assert "hashed_password" not in body

    async def test_register_duplicate_email_returns_409(self, client, existing_user):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": existing_user.email, "password": VALID_PASSWORD},
        )
        assert resp.status_code == 409
        assert resp.json()["error"]["code"] == "EMAIL_ALREADY_EXISTS"

    async def test_register_weak_password_returns_422(self, client):
        resp = await client.post(
            "/api/v1/auth/register",
            json={"email": "weak@example.com", "password": "weak"},
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_succeeds_with_correct_credentials(self, client, existing_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]
        assert body["refresh_token"]

    async def test_login_fails_with_wrong_password(self, client, existing_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "WrongPassword!"},
        )
        assert resp.status_code == 401
        assert resp.json()["error"]["code"] == "INVALID_CREDENTIALS"

    async def test_login_fails_for_unknown_user(self, client):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@example.com", "password": "whatever123!A"},
        )
        assert resp.status_code == 401


class TestProtectedRoutes:
    async def test_get_me_requires_authentication(self, client):
        resp = await client.get("/api/v1/users/me")
        assert resp.status_code in (401, 403)  # 403 if bearer header missing entirely

    async def test_get_me_returns_current_user_with_valid_token(self, client, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        access_token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/users/me", headers={"Authorization": f"Bearer {access_token}"}
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == existing_user.email

    async def test_get_me_rejects_invalid_token(self, client):
        resp = await client.get(
            "/api/v1/users/me", headers={"Authorization": "Bearer not-a-real-token"}
        )
        assert resp.status_code == 401


class TestRefreshAndLogout:
    async def test_refresh_rotates_and_returns_new_tokens(self, client, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        old_refresh = login_resp.json()["refresh_token"]

        refresh_resp = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
        )
        assert refresh_resp.status_code == 200
        new_tokens = refresh_resp.json()
        assert new_tokens["refresh_token"] != old_refresh

    async def test_reusing_rotated_refresh_token_fails(self, client, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        old_refresh = login_resp.json()["refresh_token"]

        # First use rotates it successfully.
        await client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})

        # Second use of the SAME (now-revoked) token must fail.
        replay_resp = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": old_refresh}
        )
        assert replay_resp.status_code == 401

    async def test_logout_revokes_refresh_token(self, client, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        refresh_token = login_resp.json()["refresh_token"]

        logout_resp = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": refresh_token}
        )
        assert logout_resp.status_code == 200

        reuse_resp = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert reuse_resp.status_code == 401


class TestAdminAccess:
    async def test_regular_user_cannot_list_users(self, client, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403

    async def test_admin_can_list_users(self, client, admin_user, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "AdminP@ss1"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            "/api/v1/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] >= 2
