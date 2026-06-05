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
"""SSO/LDAP endpoint tests — Phase 2."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.service import AuthError, LoginResult
from app.main import app
from app.models.tenant import AuthMode, Tenant, TenantSettings, TenantStatus
from app.models.user import SystemRole, User, UserStatus
from app.seed import DEMO_TENANT_ID

client = TestClient(app, follow_redirects=False)


@pytest.fixture
def fake_redis() -> MagicMock:
    mock = MagicMock()
    mock.get.return_value = None
    with patch("app.auth.session.get_redis_client", return_value=mock):
        yield mock


def _demo_user() -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username="cntt.cv@demo-corp",
        email="cntt.cv@demo-corp.local",
        display_name="CNTT CV",
        password_hash=None,
        system_role=SystemRole.CNTT_CHUYENVIEN,
        status=UserStatus.ACTIVE,
    )


def _demo_tenant() -> Tenant:
    return Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-corp",
        name="Demo Corporation",
        status=TenantStatus.ACTIVE,
    )


def _demo_settings(*, sso: bool = False, mode: AuthMode = AuthMode.LOCAL) -> TenantSettings:
    return TenantSettings(
        tenant_id=DEMO_TENANT_ID,
        sso_ldap_enabled=sso,
        auth_mode=mode,
        sso_config=None,
    )


def test_login_options_sso_off() -> None:
    with patch(
        "app.api.sso.get_login_options",
        return_value={
            "tenant_slug": "demo-corp",
            "tenant_name": "Demo Corporation",
            "sso_enabled": False,
            "auth_mode": "local",
            "sso_primary": False,
            "show_local_login": True,
            "branding": None,
        },
    ):
        response = client.get("/auth/login-options", params={"tenant_slug": "demo-corp"})
    assert response.status_code == 200
    data = response.json()
    assert data["sso_enabled"] is False
    assert data["show_local_login"] is True


def test_login_options_sso_oidc() -> None:
    with patch(
        "app.api.sso.get_login_options",
        return_value={
            "tenant_slug": "demo-corp",
            "tenant_name": "Demo Corporation",
            "sso_enabled": True,
            "auth_mode": "oidc",
            "sso_primary": True,
            "show_local_login": False,
            "branding": None,
        },
    ):
        response = client.get("/auth/login-options", params={"tenant_slug": "demo-corp"})
    assert response.status_code == 200
    data = response.json()
    assert data["sso_primary"] is True


def test_sso_login_redirect() -> None:
    with patch(
        "app.api.sso.start_oidc_login",
        return_value=MagicMock(redirect_url="https://idp.example/authorize"),
    ):
        response = client.get(
            "/auth/sso/login", params={"tenant_slug": "demo-corp"}
        )
    assert response.status_code == 302
    assert "idp.example" in response.headers["location"]


def test_sso_callback_sets_cookie(fake_redis: MagicMock) -> None:
    user = _demo_user()
    tenant = _demo_tenant()
    settings = _demo_settings(sso=True, mode=AuthMode.OIDC)

    with patch(
        "app.api.sso.complete_oidc_callback",
        return_value=LoginResult(
            session_id="sso-session",
            ttl_seconds=28800,
            user=user,
            tenant=tenant,
            settings=settings,
        ),
    ):
        response = client.get(
            "/auth/sso/callback",
            params={"code": "abc", "state": "xyz"},
        )
    assert response.status_code == 302
    assert "portal_session" in response.cookies


def test_sso_login_disabled() -> None:
    with patch(
        "app.api.sso.start_oidc_login",
        side_effect=AuthError("SSO is not enabled for this tenant", status_code=403),
    ):
        response = client.get(
            "/auth/sso/login", params={"tenant_slug": "demo-corp"}
        )
    assert response.status_code == 403
