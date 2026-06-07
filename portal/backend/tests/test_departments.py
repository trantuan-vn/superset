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
"""Department and user admin tests — Phase 4."""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import require_tenant_admin_or_cntt_lanhdao
from app.departments.service import DeptError
from app.main import app
from app.models.department import Department, DepartmentStatus, DeptRole
from app.models.provisioning_sync_log import ProvisioningSyncStatus
from app.provisioning.service import ProvisioningResult
from app.models.user import SystemRole, User, UserStatus
from app.seed import DEMO_TENANT_ID

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


def _sample_dept() -> Department:
    return Department(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        code="KETOAN",
        name="Phòng Kế toán",
        status=DepartmentStatus.ACTIVE,
    )


def test_list_departments_requires_auth() -> None:
    response = client.get("/departments")
    assert response.status_code == 401


def test_list_departments_as_admin() -> None:
    admin = _admin()
    dept = _sample_dept()
    app.dependency_overrides[require_tenant_admin_or_cntt_lanhdao] = lambda: admin
    try:
        with patch(
            "app.api.departments.list_departments",
            return_value=[dept],
        ):
            response = client.get("/departments")
        assert response.status_code == 200
        body = response.json()
        assert len(body) == 1
        assert body[0]["code"] == "KETOAN"
        assert body[0]["status"] == "active"
    finally:
        app.dependency_overrides.clear()


def test_create_department_as_admin() -> None:
    admin = _admin()
    dept = _sample_dept()
    app.dependency_overrides[require_tenant_admin_or_cntt_lanhdao] = lambda: admin
    try:
        with patch(
            "app.api.departments.create_department",
            return_value=dept,
        ), patch(
            "app.api.departments.ProvisioningService.department_provisioning_summary",
            return_value=ProvisioningResult(
                entity_key="KETOAN",
                status=ProvisioningSyncStatus.SKIPPED,
            ),
        ):
            response = client.post(
                "/departments",
                json={"code": "KETOAN", "name": "Phòng Kế toán"},
            )
        assert response.status_code == 201
        body = response.json()
        assert body["code"] == "KETOAN"
        assert body["provisioning"]["status"] == "skipped"
    finally:
        app.dependency_overrides.clear()


def test_deactivate_department() -> None:
    admin = _admin()
    dept = _sample_dept()
    dept.status = DepartmentStatus.INACTIVE
    app.dependency_overrides[require_tenant_admin_or_cntt_lanhdao] = lambda: admin
    try:
        with patch(
            "app.api.departments.update_department",
            return_value=dept,
        ):
            response = client.patch(
                f"/departments/{dept.id}",
                json={"status": "inactive"},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "inactive"
    finally:
        app.dependency_overrides.clear()


def test_normalize_code_rejects_invalid() -> None:
    from app.departments.service import _normalize_code

    with pytest.raises(DeptError):
        _normalize_code("bad code!")


def test_assign_dept_role_rejects_second_department() -> None:
    from unittest.mock import MagicMock

    from app.departments.service import assign_dept_role
    from app.models.department import UserDeptRole

    admin = _admin()
    dept_a = _sample_dept()
    dept_b = Department(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        code="NHANSU",
        name="Nhân sự",
        status=DepartmentStatus.ACTIVE,
    )
    dept_user = User(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username="nv@demo-corp",
        email="nv@demo-corp",
        display_name="NV",
        password_hash="x",
        system_role=SystemRole.DEPT_USER,
        status=UserStatus.ACTIVE,
    )
    dept_user.dept_roles = [
        UserDeptRole(
            user_id=dept_user.id,
            department_id=dept_a.id,
            role=DeptRole.CHUYENVIEN,
            department=dept_a,
        )
    ]

    db = MagicMock()
    with (
        patch("app.departments.service.get_user_in_tenant", return_value=dept_user),
        patch("app.departments.service.get_department", return_value=dept_b),
    ):
        with pytest.raises(DeptError) as exc_info:
            assign_dept_role(
                db,
                tenant_id=DEMO_TENANT_ID,
                user_id=dept_user.id,
                department_id=dept_b.id,
                role=DeptRole.CHUYENVIEN,
                actor=admin,
            )
    assert exc_info.value.status_code == 409
