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
"""Tenant settings API tests — Phase 2."""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth.dependencies import require_tenant_admin
from app.main import app
from app.models.tenant import AuthMode, TenantSettings
from app.models.user import SystemRole, User, UserStatus
from app.seed import DEMO_TENANT_ID
from app.tenants.service import settings_to_response

client = TestClient(app)


def _admin() -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username="admin@demo-corp",
        email="admin@demo-corp",
        display_name="Admin",
        password_hash="x",
        system_role=SystemRole.TENANT_ADMIN,
        status=UserStatus.ACTIVE,
    )


def test_settings_masks_secrets() -> None:
    settings = TenantSettings(
        tenant_id=DEMO_TENANT_ID,
        sso_ldap_enabled=True,
        auth_mode=AuthMode.LDAP,
        sso_config={
            "provider": "ldap",
            "bind_password": "secret-value",
            "bind_password_ref": "secret/portal/ldap-bind",
        },
    )
    response = settings_to_response(settings)
    assert response["sso_config"]["bind_password_set"] is True
    assert response["sso_config"]["bind_password"] == "********"


def test_get_settings_requires_admin() -> None:
    response = client.get(f"/tenants/{DEMO_TENANT_ID}/settings")
    assert response.status_code == 401


def test_patch_settings_as_admin() -> None:
    admin = _admin()
    settings = TenantSettings(
        tenant_id=DEMO_TENANT_ID,
        sso_ldap_enabled=True,
        auth_mode=AuthMode.LDAP,
        digital_signature_enabled=False,
        ai_enabled=False,
        download_token_ttl_hours=24,
    )

    app.dependency_overrides[require_tenant_admin] = lambda: admin
    try:
        with (
            patch(
                "app.api.tenants.update_tenant_settings",
                return_value=settings,
            ),
            patch(
                "app.api.tenants.settings_to_response",
                return_value=settings_to_response(settings),
            ),
        ):
            response = client.patch(
                f"/tenants/{DEMO_TENANT_ID}/settings",
                json={"sso_ldap_enabled": True, "auth_mode": "ldap"},
            )
        assert response.status_code == 200
        assert response.json()["sso_ldap_enabled"] is True
        assert response.json()["auth_mode"] == "ldap"
    finally:
        app.dependency_overrides.clear()
