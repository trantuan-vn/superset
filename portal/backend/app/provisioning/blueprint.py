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
# Dept roles use an explicit allowlist instead of cloning Gamma (SPEC §6.2).
_BLUEPRINT_BASE_ROLES: dict[RoleBlueprint, tuple[str, ...]] = {
    RoleBlueprint.CNTT_CV: ("Alpha", "sql_lab"),
    RoleBlueprint.CNTT_LD: ("Alpha",),
    RoleBlueprint.DEPT_CV: (),
    RoleBlueprint.DEPT_LD: (),
}

# Permission names stripped from every Portal-managed role (including CNTT).
_EXPORT_PERMISSION_PREFIXES = (
    "can_export",
    "can_csv",
    "can_download",
)

# Dept users: view shared dashboards only (SPEC §6.2).
# Aligned with Superset PUBLIC_ROLE_PERMISSIONS plus dataset read and session basics.
# No menu_access, SQL Lab, Explore write, or export permissions.
_DEPT_VIEW_PERMISSIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("can_read", "Dashboard"),
        ("can_read", "Chart"),
        ("can_read", "Dataset"),
        ("can_dashboard", "Superset"),
        ("can_slice", "Superset"),
        ("can_explore_json", "Superset"),
        ("can_dashboard_permalink", "Superset"),
        ("can_read", "DashboardPermalinkRestApi"),
        ("can_read", "DashboardFilterStateRestApi"),
        ("can_write", "DashboardFilterStateRestApi"),
        ("can_time_range", "Api"),
        ("can_query_form_data", "Api"),
        ("can_query", "Api"),
        ("can_read", "CssTemplate"),
        ("can_read", "Theme"),
        ("can_read", "EmbeddedDashboard"),
        ("can_read", "CurrentUserRestApi"),
        ("can_get", "Datasource"),
        ("can_external_metadata", "Datasource"),
        ("can_read", "Annotation"),
        ("can_read", "AnnotationLayerRestApi"),
        ("can_read", "ExplorePermalinkRestApi"),
        ("can_recent_activity", "Log"),
        ("can_userinfo", "UserDBModelView"),
    }
)

# Dept leaders may export from Superset dashboards/charts (not SQL Lab).
# Omit can_export on Dashboard to avoid "Export as Example" / YAML zip flows.
_DEPT_LD_EXPORT_PERMISSIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("can_export", "Chart"),
        ("can_csv", "Superset"),
        ("can_export_data", "Superset"),
        ("can_export_image", "Superset"),
    }
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


def is_dept_blueprint(blueprint: RoleBlueprint) -> bool:
    return blueprint in (RoleBlueprint.DEPT_CV, RoleBlueprint.DEPT_LD)


def dept_view_permission_allowed(
    permission_name: str,
    view_menu: str,
    *,
    blueprint: RoleBlueprint,
) -> bool:
    """Return True when a permission may be granted to a dept CV/LD role."""
    if (permission_name, view_menu) in _DEPT_VIEW_PERMISSIONS:
        return True
    if blueprint == RoleBlueprint.DEPT_LD:
        return (permission_name, view_menu) in _DEPT_LD_EXPORT_PERMISSIONS
    return False


def inactive_role_name(role_name: str) -> str:
    canonical = active_role_name(role_name)
    return f"{canonical}{_INACTIVE_SUFFIX}"


def superset_username(tenant_slug: str, portal_username: str) -> str:
    """Unique Superset username scoped to tenant."""
    return f"t_{tenant_slug}__{portal_username}"


def superset_username_candidates(
    tenant_slug: str,
    *,
    portal_username: str,
    email: str | None = None,
) -> list[str]:
    """Portal usernames that may map to the same Superset account."""
    seen: set[str] = set()
    candidates: list[str] = []

    def add(portal_name: str) -> None:
        normalized = portal_name.strip()
        if not normalized:
            return
        ss_name = superset_username(tenant_slug, normalized)
        if ss_name not in seen:
            seen.add(ss_name)
            candidates.append(ss_name)

    if portal_username.endswith(".local"):
        add(portal_username[: -len(".local")])
    add(portal_username)
    if email and email.strip().lower() != portal_username.strip().lower():
        add(email.strip().lower())

    return candidates


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
