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
"""RLS rule naming and clause templates — Portal Phase 6."""

from __future__ import annotations

import re

# Mirrors superset.portal_rls.attributes — kept in sync for portal-side tests.
_USERNAME_RE = re.compile(r"^t_(?P<tenant>[^_]+)__(?P<portal>.+)$")
_DEPT_ROLE_RE = re.compile(
    r"^t_(?P<tenant>[^_]+)_d_(?P<dept>[^_]+)_(?:cv|ld)(?:__inactive)?$"
)
_CNTT_ROLE_RE = re.compile(
    r"^t_(?P<tenant>[^_]+)_cntt_(?:cv|ld)(?:__inactive)?$"
)

RLS_FILTER_TYPE_REGULAR = "Regular"


def dept_rls_rule_name(tenant_slug: str, dept_code: str) -> str:
    return f"rls_t_{tenant_slug}_d_{dept_code}"


def tenant_rls_rule_name(tenant_slug: str) -> str:
    return f"rls_t_{tenant_slug}_tenant"


def dept_rls_clause() -> str:
    return (
        "tenant_id = '{{ current_user_tenant() }}' "
        "AND dept_code = '{{ current_user_dept() }}'"
    )


def tenant_rls_clause() -> str:
    """Tenant-wide RLS for CNTT roles (all departments within tenant)."""
    return "tenant_id = '{{ current_user_tenant() }}'"


def tenant_from_username(username: str) -> str | None:
    match = _USERNAME_RE.match(username or "")
    if match is None:
        return None
    return match.group("tenant")


def tenant_from_role_names(role_names: list[str]) -> str | None:
    for name in role_names:
        for pattern in (_DEPT_ROLE_RE, _CNTT_ROLE_RE):
            match = pattern.match(name)
            if match is not None:
                return match.group("tenant")
    return None


def dept_from_role_names(role_names: list[str]) -> str | None:
    for name in role_names:
        match = _DEPT_ROLE_RE.match(name)
        if match is not None:
            return match.group("dept")
    return None
