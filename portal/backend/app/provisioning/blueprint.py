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
"""Superset role naming and permission blueprints — SPEC §6."""

from enum import Enum

from app.models.department import DeptRole
from app.models.user import SystemRole, User


class RoleBlueprint(str, Enum):
    """Permission templates cloned from built-in Superset roles."""

    CNTT_CV = "cntt_cv"
    CNTT_LD = "cntt_ld"
    DEPT_CV = "dept_cv"
    DEPT_LD = "dept_ld"


# Base Superset roles whose permissions are merged for each blueprint.
_BLUEPRINT_BASE_ROLES: dict[RoleBlueprint, tuple[str, ...]] = {
    RoleBlueprint.CNTT_CV: ("Alpha", "sql_lab"),
    RoleBlueprint.CNTT_LD: ("Alpha",),
    RoleBlueprint.DEPT_CV: ("Gamma",),
    RoleBlueprint.DEPT_LD: ("Gamma",),
}

# Permission names that must never be granted to Portal-managed roles.
_EXPORT_PERMISSION_PREFIXES = (
    "can_export",
    "can_csv",
    "can_download",
)


def cntt_cv_role_name(tenant_slug: str) -> str:
    return f"t_{tenant_slug}_cntt_cv"


def cntt_ld_role_name(tenant_slug: str) -> str:
    return f"t_{tenant_slug}_cntt_ld"


def dept_cv_role_name(tenant_slug: str, dept_code: str) -> str:
    return f"t_{tenant_slug}_d_{dept_code}_cv"


def dept_ld_role_name(tenant_slug: str, dept_code: str) -> str:
    return f"t_{tenant_slug}_d_{dept_code}_ld"


def dept_role_names(tenant_slug: str, dept_code: str) -> tuple[str, str]:
    return (
        dept_cv_role_name(tenant_slug, dept_code),
        dept_ld_role_name(tenant_slug, dept_code),
    )


def tenant_cntt_role_names(tenant_slug: str) -> tuple[str, str]:
    return (cntt_cv_role_name(tenant_slug), cntt_ld_role_name(tenant_slug))


_INACTIVE_SUFFIX = "__inactive"


def active_role_name(role_name: str) -> str:
    """Strip soft-deactivate suffix so blueprint/name helpers see the canonical role."""
    if role_name.endswith(_INACTIVE_SUFFIX):
        return role_name[: -len(_INACTIVE_SUFFIX)]
    return role_name


def blueprint_for_role_name(role_name: str) -> RoleBlueprint | None:
    canonical = active_role_name(role_name)
    if canonical.endswith("_cntt_cv"):
        return RoleBlueprint.CNTT_CV
    if canonical.endswith("_cntt_ld"):
        return RoleBlueprint.CNTT_LD
    if canonical.endswith("_cv"):
        return RoleBlueprint.DEPT_CV
    if canonical.endswith("_ld"):
        return RoleBlueprint.DEPT_LD
    return None


def base_roles_for_blueprint(blueprint: RoleBlueprint) -> tuple[str, ...]:
    return _BLUEPRINT_BASE_ROLES[blueprint]


def is_export_permission(permission_name: str) -> bool:
    lowered = permission_name.lower()
    return any(lowered.startswith(prefix) for prefix in _EXPORT_PERMISSION_PREFIXES)


def inactive_role_name(role_name: str) -> str:
    canonical = active_role_name(role_name)
    return f"{canonical}{_INACTIVE_SUFFIX}"


def superset_username(tenant_slug: str, portal_username: str) -> str:
    """Unique Superset username scoped to tenant."""
    return f"t_{tenant_slug}__{portal_username}"


def portal_user_needs_superset_sync(user: User) -> bool:
    """Only CNTT and dept users receive Superset accounts."""
    return user.system_role in {
        SystemRole.CNTT_CHUYENVIEN,
        SystemRole.CNTT_LANHDAO,
        SystemRole.DEPT_USER,
    }


def superset_role_names_for_user(
    tenant_slug: str,
    system_role: SystemRole,
    *,
    dept_code: str | None = None,
    dept_role: DeptRole | None = None,
) -> list[str]:
    """Map a Portal user to one or more Superset role names."""
    if system_role == SystemRole.CNTT_CHUYENVIEN:
        return [cntt_cv_role_name(tenant_slug)]
    if system_role == SystemRole.CNTT_LANHDAO:
        return [cntt_ld_role_name(tenant_slug)]
    if system_role == SystemRole.DEPT_USER and dept_code and dept_role:
        if dept_role == DeptRole.CHUYENVIEN:
            return [dept_cv_role_name(tenant_slug, dept_code)]
        return [dept_ld_role_name(tenant_slug, dept_code)]
    return []
