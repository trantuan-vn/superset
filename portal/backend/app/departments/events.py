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
"""Domain events for department lifecycle — Phase 4."""

from dataclasses import dataclass
from typing import Callable

from app.models.department import Department


@dataclass(frozen=True)
class DepartmentCreated:
    """Emitted when a new department is created within a tenant."""

    department: Department
    tenant_slug: str


_department_created_handlers: list[Callable[[DepartmentCreated], None]] = []


def on_department_created(handler: Callable[[DepartmentCreated], None]) -> None:
    """Register a handler for DepartmentCreated events (Phase 5 provisioning)."""
    _department_created_handlers.append(handler)


def emit_department_created(event: DepartmentCreated) -> None:
    """Dispatch DepartmentCreated to registered handlers."""
    for handler in _department_created_handlers:
        handler(event)
