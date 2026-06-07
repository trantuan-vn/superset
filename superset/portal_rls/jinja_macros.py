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
"""Jinja macros for Portal multi-tenant RLS — Phase 6.

Registered in Superset config via ``JINJA_CONTEXT_ADDONS``::

    from superset.portal_rls.jinja_macros import (
        current_user_dept,
        current_user_tenant,
    )

    JINJA_CONTEXT_ADDONS = {
        "current_user_tenant": current_user_tenant,
        "current_user_dept": current_user_dept,
    }

Policy (Gate 6):
- ``dept_user`` roles → tenant + department filter (via dept role name).
- ``cntt_*`` roles → tenant-wide visibility (``current_user_dept()`` returns empty).
"""

from __future__ import annotations

from flask import g
from superset import security_manager

from superset.portal_rls.attributes import resolve_dept_code, resolve_tenant_slug


def _role_names() -> list[str]:
    try:
        return [role.name for role in security_manager.get_user_roles()]
    except Exception:  # pylint: disable=broad-except
        return []


def _username() -> str:
    user = getattr(g, "user", None)
    if user is None:
        return ""
    return str(getattr(user, "username", "") or "")


def current_user_tenant() -> str:
    """Return tenant slug for the logged-in Portal-provisioned Superset user."""
    return resolve_tenant_slug(_username(), _role_names())


def current_user_dept() -> str:
    """Return department code for dept-scoped users; empty for CNTT roles."""
    return resolve_dept_code(_role_names())
