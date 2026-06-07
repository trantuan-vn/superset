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
"""Resolve Portal tenant/dept scope from Superset usernames and role names."""

from __future__ import annotations

import re

# Portal-provisioned Superset username: t_{tenant_slug}__{portal_username}
_USERNAME_RE = re.compile(r"^t_(?P<tenant>[^_]+)__(?P<portal>.+)$")

# Dept role: t_{tenant_slug}_d_{DEPT_CODE}_{cv|ld}[, __inactive]
_DEPT_ROLE_RE = re.compile(
    r"^t_(?P<tenant>[^_]+)_d_(?P<dept>[^_]+)_(?:cv|ld)(?:__inactive)?$"
)

# CNTT role: t_{tenant_slug}_cntt_{cv|ld}[, __inactive]
_CNTT_ROLE_RE = re.compile(
    r"^t_(?P<tenant>[^_]+)_cntt_(?:cv|ld)(?:__inactive)?$"
)


def tenant_from_username(username: str) -> str | None:
    """Extract tenant slug from a Portal-provisioned Superset username."""
    match = _USERNAME_RE.match(username or "")
    if match is None:
        return None
    return match.group("tenant")


def tenant_from_role_names(role_names: list[str]) -> str | None:
    """Infer tenant slug from Portal-managed Superset role names."""
    for name in role_names:
        for pattern in (_DEPT_ROLE_RE, _CNTT_ROLE_RE):
            match = pattern.match(name)
            if match is not None:
                return match.group("tenant")
    return None


def dept_from_role_names(role_names: list[str]) -> str | None:
    """Extract department code from dept-scoped Superset roles."""
    for name in role_names:
        match = _DEPT_ROLE_RE.match(name)
        if match is not None:
            return match.group("dept")
    return None


def resolve_tenant_slug(username: str, role_names: list[str]) -> str:
    """Return tenant slug for the current user, or empty string if unknown."""
    return tenant_from_username(username) or tenant_from_role_names(role_names) or ""


def resolve_dept_code(role_names: list[str]) -> str:
    """Return department code for dept users; empty for CNTT (tenant-wide)."""
    return dept_from_role_names(role_names) or ""
