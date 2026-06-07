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
"""Platform operator API tests."""

import uuid
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.auth.dependencies import get_current_user
from app.main import app
from app.models.user import SystemRole, User, UserStatus
from app.seed import PLATFORM_TENANT_ID

client = TestClient(app)


def _platform_admin() -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=PLATFORM_TENANT_ID,
        username="admin@platform",
        email="admin@platform",
        display_name="Platform Admin",
        password_hash="hashed",
        system_role=SystemRole.PLATFORM_ADMIN,
        status=UserStatus.ACTIVE,
    )


def test_platform_tenants_requires_platform_admin() -> None:
    tenant_admin = User(
        id=uuid.uuid4(),
        tenant_id=uuid.uuid4(),
        username="admin@demo",
        email="admin@demo",
        display_name="Tenant Admin",
        password_hash="hashed",
        system_role=SystemRole.TENANT_ADMIN,
        status=UserStatus.ACTIVE,
    )
    app.dependency_overrides[get_current_user] = lambda: tenant_admin
    try:
        response = client.get("/platform/tenants")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_platform_tenants_list_ok() -> None:
    app.dependency_overrides[get_current_user] = lambda: _platform_admin()
    db = MagicMock()
    from app.db import get_db

    app.dependency_overrides[get_db] = lambda: db

    with patch("app.api.platform.list_tenants", return_value=[]):
        try:
            response = client.get("/platform/tenants")
            assert response.status_code == 200
            assert response.json() == []
        finally:
            app.dependency_overrides.clear()
