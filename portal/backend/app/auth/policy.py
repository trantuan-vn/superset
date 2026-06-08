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
"""Authorization policy — role × department matrix (SPEC §11.1)."""

from enum import Enum

from app.models.department import DeptRole, UserDeptRole
from app.models.user import SystemRole, User


class Capability(str, Enum):
    """High-level capabilities enforced by API dependencies."""

    PLATFORM_TENANTS = "platform.tenants"
    TENANT_SETTINGS = "tenant.settings"
    IAM_ADMIN = "iam.admin"
    CNTT_TEMPLATES = "cntt.templates"
    CNTT_APPROVALS = "cntt.approvals"
    DEPT_TEMPLATES = "dept.templates"
    DEPT_TRANSACTIONS = "dept.transactions"
    DEPT_APPROVALS = "dept.approvals"
    AUDIT_READ = "audit.read"


# system_role → capabilities (department-scoped capabilities checked separately)
_SYSTEM_ROLE_CAPABILITIES: dict[SystemRole, frozenset[Capability]] = {
    SystemRole.PLATFORM_ADMIN: frozenset({Capability.PLATFORM_TENANTS}),
    SystemRole.TENANT_ADMIN: frozenset(
        {
            Capability.TENANT_SETTINGS,
            Capability.IAM_ADMIN,
            Capability.AUDIT_READ,
        }
    ),
    SystemRole.CNTT_LANHDAO: frozenset(
        {
            Capability.IAM_ADMIN,
            Capability.CNTT_TEMPLATES,
            Capability.CNTT_APPROVALS,
            Capability.AUDIT_READ,
        }
    ),
    SystemRole.CNTT_CHUYENVIEN: frozenset({Capability.CNTT_TEMPLATES}),
    SystemRole.DEPT_USER: frozenset(),
}

# Roles a principal may assign when creating/updating users (IAM admin scope)
IAM_ASSIGNABLE_ROLES: frozenset[SystemRole] = frozenset(
    {
        SystemRole.DEPT_USER,
        SystemRole.CNTT_CHUYENVIEN,
        SystemRole.CNTT_LANHDAO,
        SystemRole.TENANT_ADMIN,
    }
)

TENANT_ADMIN_ONLY_ASSIGNABLE: frozenset[SystemRole] = frozenset(
    {SystemRole.TENANT_ADMIN}
)


def dept_roles(user: User) -> list[UserDeptRole]:
    return list(getattr(user, "dept_roles", []) or [])


def has_dept_assignment(user: User) -> bool:
    return len(dept_roles(user)) > 0


def is_dept_leader(user: User) -> bool:
    return any(r.role == DeptRole.LANHDAO for r in dept_roles(user))


def is_dept_specialist(user: User) -> bool:
    return any(r.role == DeptRole.CHUYENVIEN for r in dept_roles(user))


def has_capability(user: User, capability: Capability) -> bool:
    base = _SYSTEM_ROLE_CAPABILITIES.get(user.system_role, frozenset())
    if capability in base:
        return True

    if user.system_role != SystemRole.DEPT_USER:
        return False

    if not has_dept_assignment(user):
        return False

    if capability == Capability.DEPT_TEMPLATES:
        return is_dept_specialist(user) or is_dept_leader(user)

    if capability == Capability.DEPT_TRANSACTIONS:
        return is_dept_specialist(user)

    if capability == Capability.DEPT_APPROVALS:
        return is_dept_leader(user)

    return False


def can_assign_system_role(actor: User, target_role: SystemRole) -> bool:
    if target_role == SystemRole.PLATFORM_ADMIN:
        return False
    if target_role not in IAM_ASSIGNABLE_ROLES:
        return False
    if target_role in TENANT_ADMIN_ONLY_ASSIGNABLE:
        return actor.system_role == SystemRole.TENANT_ADMIN
    return has_capability(actor, Capability.IAM_ADMIN)


def can_modify_user(actor: User, target: User) -> bool:
    if not has_capability(actor, Capability.IAM_ADMIN):
        return False
    if target.system_role == SystemRole.PLATFORM_ADMIN:
        return False
    if (
        target.system_role == SystemRole.TENANT_ADMIN
        and actor.system_role != SystemRole.TENANT_ADMIN
    ):
        return False
    return True


def route_capability(path: str) -> Capability | None:
    """Map frontend route prefix to a capability (SPEC §11.1)."""
    normalized = path.rstrip("/") or "/"
    if normalized.startswith("/platform/tenants"):
        return Capability.PLATFORM_TENANTS
    if normalized.startswith("/admin/settings"):
        return Capability.TENANT_SETTINGS
    if normalized.startswith("/admin/departments") or normalized.startswith("/admin/users"):
        return Capability.IAM_ADMIN
    if normalized.startswith("/cntt/templates"):
        return Capability.CNTT_TEMPLATES
    if normalized.startswith("/cntt/approvals"):
        return Capability.CNTT_APPROVALS
    if normalized.startswith("/dept/templates"):
        return Capability.DEPT_TEMPLATES
    if normalized.startswith("/dept/transactions"):
        return Capability.DEPT_TRANSACTIONS
    if normalized.startswith("/dept/approvals"):
        return Capability.DEPT_APPROVALS
    if normalized.startswith("/audit"):
        return Capability.AUDIT_READ
    return None


def can_access_route(user: User, path: str) -> bool:
    capability = route_capability(path)
    if capability is None:
        return True
    return has_capability(user, capability)
