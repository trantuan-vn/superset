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
"""Event handlers wiring Portal lifecycle → ProvisioningService."""

from __future__ import annotations

import logging

from sqlalchemy import select

from app.db import SessionLocal
from app.departments.events import DepartmentCreated, on_department_created
from app.models.tenant import Tenant
from app.provisioning.events import (
    DepartmentDeactivated,
    DepartmentReactivated,
    TenantCreated,
    UserProvisionRequested,
    on_department_deactivated,
    on_department_reactivated,
    on_tenant_created,
    on_user_provision_requested,
)
from app.provisioning.service import ProvisioningService

logger = logging.getLogger(__name__)
_handlers_registered = False


def _with_service() -> ProvisioningService:
    db = SessionLocal()
    return ProvisioningService(db)


def _handle_department_created(event: DepartmentCreated) -> None:
    db = SessionLocal()
    try:
        service = ProvisioningService(db)
        service.provision_department_roles(
            event.tenant_slug,
            event.department.tenant_id,
            event.department.code,
        )
    except Exception:
        logger.exception(
            "Failed to provision dept roles for %s",
            event.department.code,
        )
    finally:
        db.close()


def _handle_tenant_created(event: TenantCreated) -> None:
    db = SessionLocal()
    try:
        service = ProvisioningService(db)
        service.provision_tenant_roles(event.tenant.slug, event.tenant.id)
    except Exception:
        logger.exception("Failed to provision tenant roles for %s", event.tenant.slug)
    finally:
        db.close()


def _handle_department_deactivated(event: DepartmentDeactivated) -> None:
    db = SessionLocal()
    try:
        service = ProvisioningService(db)
        service.deactivate_department_roles(
            event.tenant_slug,
            event.department.tenant_id,
            event.department.code,
        )
    except Exception:
        logger.exception(
            "Failed to deactivate dept roles for %s",
            event.department.code,
        )
    finally:
        db.close()


def _handle_department_reactivated(event: DepartmentReactivated) -> None:
    db = SessionLocal()
    try:
        service = ProvisioningService(db)
        service.reactivate_department_roles(
            event.tenant_slug,
            event.department.tenant_id,
            event.department.code,
        )
    except Exception:
        logger.exception(
            "Failed to reactivate dept roles for %s",
            event.department.code,
        )
    finally:
        db.close()


def _handle_user_provision_requested(event: UserProvisionRequested) -> None:
    db = SessionLocal()
    try:
        service = ProvisioningService(db)
        service.sync_user_by_id(event.user_id)
    except Exception:
        logger.exception("Failed to sync user %s to Superset", event.user_id)
    finally:
        db.close()


def register_provisioning_handlers() -> None:
    """Register lifecycle handlers once at application startup."""
    global _handlers_registered  # noqa: PLW0603
    if _handlers_registered:
        return

    on_department_created(_handle_department_created)
    on_tenant_created(_handle_tenant_created)
    on_department_deactivated(_handle_department_deactivated)
    on_department_reactivated(_handle_department_reactivated)
    on_user_provision_requested(_handle_user_provision_requested)
    _handlers_registered = True


def bootstrap_existing_tenants() -> None:
    """Reconcile roles/users for tenants created before provisioning was enabled."""
    db = SessionLocal()
    try:
        service = ProvisioningService(db)
        if not service.enabled:
            return
        tenants = db.scalars(
            select(Tenant).where(Tenant.slug != "platform")
        ).all()
        for tenant in tenants:
            try:
                service.reconcile_tenant(tenant.id)
            except Exception:
                logger.exception("Bootstrap provisioning failed for %s", tenant.slug)
    finally:
        db.close()
