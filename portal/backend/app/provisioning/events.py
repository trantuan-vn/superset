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
"""Domain events for Superset provisioning — Phase 5."""

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from app.models.department import Department, DeptRole
from app.models.tenant import Tenant
from app.models.user import User


@dataclass(frozen=True)
class TenantCreated:
    tenant: Tenant


@dataclass(frozen=True)
class DepartmentDeactivated:
    department: Department
    tenant_slug: str


@dataclass(frozen=True)
class DepartmentReactivated:
    department: Department
    tenant_slug: str


@dataclass(frozen=True)
class UserProvisionRequested:
    user_id: UUID
    tenant_slug: str
    dept_code: str | None = None
    dept_role: DeptRole | None = None
    password: str | None = None


_tenant_created_handlers: list[Callable[[TenantCreated], None]] = []
_department_deactivated_handlers: list[Callable[[DepartmentDeactivated], None]] = []
_department_reactivated_handlers: list[Callable[[DepartmentReactivated], None]] = []
_user_provision_handlers: list[Callable[[UserProvisionRequested], None]] = []


def on_tenant_created(handler: Callable[[TenantCreated], None]) -> None:
    _tenant_created_handlers.append(handler)


def on_department_deactivated(handler: Callable[[DepartmentDeactivated], None]) -> None:
    _department_deactivated_handlers.append(handler)


def on_department_reactivated(handler: Callable[[DepartmentReactivated], None]) -> None:
    _department_reactivated_handlers.append(handler)


def on_user_provision_requested(handler: Callable[[UserProvisionRequested], None]) -> None:
    _user_provision_handlers.append(handler)


def emit_tenant_created(event: TenantCreated) -> None:
    for handler in _tenant_created_handlers:
        handler(event)


def emit_department_deactivated(event: DepartmentDeactivated) -> None:
    for handler in _department_deactivated_handlers:
        handler(event)


def emit_department_reactivated(event: DepartmentReactivated) -> None:
    for handler in _department_reactivated_handlers:
        handler(event)


def emit_user_provision_requested(event: UserProvisionRequested) -> None:
    for handler in _user_provision_handlers:
        handler(event)


def request_user_provision(
    user: User,
    tenant_slug: str,
    *,
    dept_code: str | None = None,
    dept_role: DeptRole | None = None,
    password: str | None = None,
) -> None:
    """Queue a user sync after create/update/dept-role change."""
    emit_user_provision_requested(
        UserProvisionRequested(
            user_id=user.id,
            tenant_slug=tenant_slug,
            dept_code=dept_code,
            dept_role=dept_role,
            password=password,
        )
    )
