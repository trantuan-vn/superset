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
"""Authorization policy tests — SPEC §11.1."""

import uuid

from app.auth.policy import (
    Capability,
    can_access_route,
    can_assign_system_role,
    can_modify_user,
    has_capability,
)
from app.models.department import Department, DepartmentStatus, DeptRole, UserDeptRole
from app.models.user import SystemRole, User, UserStatus
from app.seed import DEMO_TENANT_ID


def _user(role: SystemRole, *, dept_role: DeptRole | None = None) -> User:
    user = User(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username="u@demo",
        email="u@demo",
        display_name="U",
        password_hash="x",
        system_role=role,
        status=UserStatus.ACTIVE,
    )
    if dept_role is not None:
        dept = Department(
            id=uuid.uuid4(),
            tenant_id=DEMO_TENANT_ID,
            code="KETOAN",
            name="Kế toán",
            status=DepartmentStatus.ACTIVE,
        )
        user.dept_roles = [
            UserDeptRole(
                user_id=user.id,
                department_id=dept.id,
                role=dept_role,
                department=dept,
            )
        ]
    else:
        user.dept_roles = []
    return user


def test_tenant_admin_capabilities() -> None:
    admin = _user(SystemRole.TENANT_ADMIN)
    assert has_capability(admin, Capability.TENANT_SETTINGS)
    assert has_capability(admin, Capability.IAM_ADMIN)
    assert not has_capability(admin, Capability.CNTT_TEMPLATES)


def test_cntt_lanhdao_iam_without_tenant_settings() -> None:
    leader = _user(SystemRole.CNTT_LANHDAO)
    assert has_capability(leader, Capability.IAM_ADMIN)
    assert has_capability(leader, Capability.CNTT_APPROVALS)
    assert not has_capability(leader, Capability.TENANT_SETTINGS)


def test_dept_user_requires_assignment_and_role() -> None:
    unassigned = _user(SystemRole.DEPT_USER)
    specialist = _user(SystemRole.DEPT_USER, dept_role=DeptRole.CHUYENVIEN)
    dept_leader = _user(SystemRole.DEPT_USER, dept_role=DeptRole.LANHDAO)

    assert not has_capability(unassigned, Capability.DEPT_TEMPLATES)
    assert has_capability(specialist, Capability.DEPT_TEMPLATES)
    assert has_capability(specialist, Capability.DEPT_TRANSACTIONS)
    assert not has_capability(specialist, Capability.DEPT_APPROVALS)
    assert has_capability(dept_leader, Capability.DEPT_APPROVALS)


def test_route_matrix() -> None:
    admin = _user(SystemRole.TENANT_ADMIN)
    cv = _user(SystemRole.CNTT_CHUYENVIEN)

    assert can_access_route(admin, "/admin/settings")
    assert can_access_route(admin, "/admin/users")
    assert not can_access_route(cv, "/admin/users")
    assert can_access_route(cv, "/cntt/templates")


def test_iam_role_assignment_restrictions() -> None:
    tenant_admin = _user(SystemRole.TENANT_ADMIN)
    cntt_ld = _user(SystemRole.CNTT_LANHDAO)

    assert can_assign_system_role(tenant_admin, SystemRole.TENANT_ADMIN)
    assert can_assign_system_role(tenant_admin, SystemRole.DEPT_USER)
    assert not can_assign_system_role(cntt_ld, SystemRole.TENANT_ADMIN)
    assert can_assign_system_role(cntt_ld, SystemRole.DEPT_USER)


def test_modify_user_restrictions() -> None:
    tenant_admin = _user(SystemRole.TENANT_ADMIN)
    cntt_ld = _user(SystemRole.CNTT_LANHDAO)
    other_admin = _user(SystemRole.TENANT_ADMIN)
    dept_user = _user(SystemRole.DEPT_USER, dept_role=DeptRole.CHUYENVIEN)

    assert can_modify_user(tenant_admin, other_admin)
    assert can_modify_user(tenant_admin, dept_user)
    assert not can_modify_user(cntt_ld, other_admin)
    assert can_modify_user(cntt_ld, dept_user)
