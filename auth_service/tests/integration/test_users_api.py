VALID_PASSWORD = "Str0ng!Pass1"


class TestUserProfile:
    async def test_update_me_changes_full_name(self, client, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.patch(
            "/api/v1/users/me",
            json={"full_name": "Updated Name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"


class TestAdminUserManagement:
    async def test_admin_can_get_specific_user(self, client, admin_user, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "AdminP@ss1"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            f"/api/v1/users/{existing_user.id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["email"] == existing_user.email

    async def test_admin_can_deactivate_user(self, client, admin_user, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "AdminP@ss1"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            f"/api/v1/users/{existing_user.id}/deactivate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        assert resp.json()["is_active"] is False

        # Deactivated user can no longer log in.
        login_after = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        assert login_after.status_code == 403

    async def test_regular_user_cannot_deactivate_others(self, client, existing_user, admin_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.post(
            f"/api/v1/users/{admin_user.id}/deactivate",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403

    async def test_get_nonexistent_user_returns_404(self, client, admin_user):
        import uuid

        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": admin_user.email, "password": "AdminP@ss1"},
        )
        token = login_resp.json()["access_token"]

        resp = await client.get(
            f"/api/v1/users/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


class TestPasswordChange:
    async def test_change_password_succeeds_and_revokes_sessions(self, client, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        access_token = login_resp.json()["access_token"]
        refresh_token = login_resp.json()["refresh_token"]

        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "StrongP@ss1", "new_password": "NewStr0ng!Pass"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200

        # Old refresh token must now be revoked.
        refresh_resp = await client.post(
            "/api/v1/auth/refresh", json={"refresh_token": refresh_token}
        )
        assert refresh_resp.status_code == 401

        # New password logs in successfully.
        new_login = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "NewStr0ng!Pass"},
        )
        assert new_login.status_code == 200

    async def test_change_password_fails_with_wrong_current_password(self, client, existing_user):
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        access_token = login_resp.json()["access_token"]

        resp = await client.post(
            "/api/v1/auth/change-password",
            json={"current_password": "WrongOne!", "new_password": "NewStr0ng!Pass"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 401

    async def test_logout_all_revokes_every_session(self, client, existing_user):
        login1 = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        login2 = await client.post(
            "/api/v1/auth/login",
            json={"email": existing_user.email, "password": "StrongP@ss1"},
        )
        access_token = login2.json()["access_token"]
        refresh1 = login1.json()["refresh_token"]
        refresh2 = login2.json()["refresh_token"]

        resp = await client.post(
            "/api/v1/auth/logout-all",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        assert resp.status_code == 200

        for token in (refresh1, refresh2):
            r = await client.post("/api/v1/auth/refresh", json={"refresh_token": token})
            assert r.status_code == 401
