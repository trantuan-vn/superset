# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Authentication endpoint tests — Phase 1."""

import os
import uuid
from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user, get_session_id
from app.auth.service import AuthError, LoginResult, MeResult
from app.main import app
from app.models.tenant import Tenant, TenantSettings, TenantStatus
from app.models.user import SystemRole, User, UserStatus
from app.seed import DEMO_TENANT_ID

client = TestClient(app)


def _demo_user() -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username="admin@demo-corp",
        email="admin@demo-corp",
        display_name="Tenant Admin",
        password_hash="hashed",
        system_role=SystemRole.TENANT_ADMIN,
        status=UserStatus.ACTIVE,
    )


def _demo_tenant() -> Tenant:
    return Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-corp",
        name="Demo Corporation",
        status=TenantStatus.ACTIVE,
    )


def _demo_settings() -> TenantSettings:
    return TenantSettings(
        tenant_id=DEMO_TENANT_ID,
        branding={"app_name": "Portal Kết xuất", "primary_color": "#1677ff"},
    )


@pytest.fixture
def fake_redis() -> Generator[MagicMock, None, None]:
    mock = MagicMock()
    mock.get.return_value = None

    def _setex(key: str, ttl: int, value: str) -> None:
        mock.get.side_effect = lambda k: value if k == key else None

    mock.setex.side_effect = _setex
    with patch("app.auth.session.get_redis_client", return_value=mock):
        yield mock


def test_me_requires_session() -> None:
    response = client.get("/auth/me")
    assert response.status_code == 401


def test_login_success_sets_cookie(fake_redis: MagicMock) -> None:
    user = _demo_user()
    tenant = _demo_tenant()
    settings = _demo_settings()
    with patch(
        "app.api.auth.login",
        return_value=LoginResult(
            session_id="session-abc",
            ttl_seconds=28800,
            user=user,
            tenant=tenant,
            settings=settings,
        ),
    ):
        response = client.post(
            "/auth/login",
            json={
                "tenant_slug": "demo-corp",
                "username": "admin@demo-corp",
                "password": "Pass123!",
            },
        )
    assert response.status_code == 200
    payload = response.json()
    assert payload["user"]["username"] == "admin@demo-corp"
    assert payload["tenant"]["slug"] == "demo-corp"
    assert "portal_session" in response.cookies


def test_login_invalid_credentials() -> None:
    with patch(
        "app.api.auth.login",
        side_effect=AuthError("Invalid username or password", status_code=401),
    ):
        response = client.post(
            "/auth/login",
            json={
                "tenant_slug": "demo-corp",
                "username": "admin@demo-corp",
                "password": "wrong",
            },
        )
    assert response.status_code == 401


def test_logout_and_me_flow(fake_redis: MagicMock) -> None:
    user = _demo_user()
    tenant = _demo_tenant()
    settings = _demo_settings()

    session_payload = (
        '{"session_id": "session-abc", "user_id": "%s", "tenant_id": "%s", '
        '"created_at": "2026-01-01T00:00:00+00:00", "expires_at": "2026-01-02T00:00:00+00:00"}'
    ) % (user.id, DEMO_TENANT_ID)

    fake_redis.get.side_effect = lambda key: (
        session_payload if key == "portal:session:session-abc" else None
    )

    app.dependency_overrides[get_session_id] = lambda: "session-abc"
    app.dependency_overrides[get_current_user] = lambda: user

    try:
        with (
            patch("app.api.auth.login", return_value=LoginResult(
                session_id="session-abc",
                ttl_seconds=28800,
                user=user,
                tenant=tenant,
                settings=settings,
            )),
            patch(
                "app.api.auth.get_me",
                return_value=MeResult(user=user, tenant=tenant, settings=settings),
            ),
            patch("app.api.auth.logout"),
        ):
            login_response = client.post(
                "/auth/login",
                json={
                    "tenant_slug": "demo-corp",
                    "username": "admin@demo-corp",
                    "password": "Pass123!",
                },
            )
            assert login_response.status_code == 200
            client.cookies.set("portal_session", "session-abc")

            me_response = client.get("/auth/me")
            assert me_response.status_code == 200
            assert me_response.json()["user"]["system_role"] == "tenant_admin"

            logout_response = client.post("/auth/logout")
            assert logout_response.status_code == 200
    finally:
        app.dependency_overrides.clear()


@pytest.mark.skipif(
    os.getenv("PORTAL_INTEGRATION_TESTS") != "1",
    reason="Set PORTAL_INTEGRATION_TESTS=1 with PostgreSQL + Redis for full auth flow",
)
def test_login_integration_postgres() -> None:
    """Run against docker stack: PORTAL_INTEGRATION_TESTS=1 pytest -k integration."""
    response = client.post(
        "/auth/login",
        json={
            "tenant_slug": "demo-corp",
            "username": "admin@demo-corp",
            "password": "Pass123!",
        },
    )
    assert response.status_code == 200
