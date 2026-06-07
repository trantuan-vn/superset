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
"""ProvisioningService — sync Portal roles/users to Superset (Phase 5)."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.config import Settings, get_settings
from app.models.department import Department, DepartmentStatus, DeptRole, UserDeptRole
from app.models.provisioning_sync_log import (
    ProvisioningEntityType,
    ProvisioningOperation,
    ProvisioningSyncLog,
    ProvisioningSyncStatus,
)
from app.models.tenant import Tenant
from app.models.user import SystemRole, User, UserStatus
from app.provisioning.blueprint import (
    RoleBlueprint,
    active_role_name,
    base_roles_for_blueprint,
    blueprint_for_role_name,
    dept_role_names,
    inactive_role_name,
    is_export_permission,
    portal_user_needs_superset_sync,
    superset_role_names_for_user,
    superset_username,
    tenant_cntt_role_names,
)
from app.provisioning.superset_client import (
    SupersetClient,
    SupersetClientError,
    SupersetRole,
    split_display_name,
)

logger = logging.getLogger(__name__)

PAGE_SIZE = 500


@dataclass(frozen=True)
class ProvisioningResult:
    entity_key: str
    status: ProvisioningSyncStatus
    superset_id: int | None = None
    message: str | None = None


class ProvisioningService:
    """Orchestrates Portal → Superset role and user synchronization."""

    def __init__(
        self,
        db: Session,
        *,
        client: SupersetClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        self._db = db
        self._settings = settings or get_settings()
        self._client = client or SupersetClient(self._settings)
        self._permission_name_cache: dict[int, str] | None = None

    @property
    def enabled(self) -> bool:
        return self._client.enabled

    def provision_tenant_roles(self, tenant_slug: str, tenant_id: uuid.UUID) -> list[ProvisioningResult]:
        """Create CNTT blueprint roles when a tenant is onboarded."""
        results: list[ProvisioningResult] = []
        for role_name in tenant_cntt_role_names(tenant_slug):
            blueprint = blueprint_for_role_name(role_name)
            if blueprint is None:
                continue
            results.append(
                self._provision_role(
                    tenant_id=tenant_id,
                    role_name=role_name,
                    blueprint=blueprint,
                    operation=ProvisioningOperation.CREATE,
                )
            )
        return results

    def provision_department_roles(
        self,
        tenant_slug: str,
        tenant_id: uuid.UUID,
        dept_code: str,
    ) -> list[ProvisioningResult]:
        """Create dept CV/LD roles when a department is created."""
        results: list[ProvisioningResult] = []
        for role_name in dept_role_names(tenant_slug, dept_code):
            blueprint = blueprint_for_role_name(role_name)
            if blueprint is None:
                continue
            results.append(
                self._provision_role(
                    tenant_id=tenant_id,
                    role_name=role_name,
                    blueprint=blueprint,
                    operation=ProvisioningOperation.CREATE,
                )
            )
        return results

    def deactivate_department_roles(
        self,
        tenant_slug: str,
        tenant_id: uuid.UUID,
        dept_code: str,
    ) -> list[ProvisioningResult]:
        """Soft-deactivate dept roles (rename + revoke user assignments)."""
        results: list[ProvisioningResult] = []
        for role_name in dept_role_names(tenant_slug, dept_code):
            results.append(
                self._deactivate_role(
                    tenant_id=tenant_id,
                    role_name=role_name,
                )
            )
        return results

    def reactivate_department_roles(
        self,
        tenant_slug: str,
        tenant_id: uuid.UUID,
        dept_code: str,
    ) -> list[ProvisioningResult]:
        """Restore dept roles from __inactive suffix and re-sync assigned users."""
        results: list[ProvisioningResult] = []
        for role_name in dept_role_names(tenant_slug, dept_code):
            blueprint = blueprint_for_role_name(role_name)
            if blueprint is None:
                continue
            results.append(
                self._provision_role(
                    tenant_id=tenant_id,
                    role_name=role_name,
                    blueprint=blueprint,
                    operation=ProvisioningOperation.UPDATE,
                )
            )
        results.extend(
            self._resync_department_users(tenant_slug, tenant_id, dept_code)
        )
        return results

    def sync_user(
        self,
        user: User,
        tenant_slug: str,
        *,
        dept_code: str | None = None,
        dept_role: DeptRole | None = None,
    ) -> ProvisioningResult:
        """Create or update a Superset user with mapped roles."""
        if not portal_user_needs_superset_sync(user):
            return ProvisioningResult(
                entity_key=str(user.id),
                status=ProvisioningSyncStatus.SKIPPED,
                message="User role does not require Superset account",
            )

        username = superset_username(tenant_slug, user.username)
        return self._sync_portal_user(
            tenant_id=user.tenant_id,
            portal_user_id=user.id,
            username=username,
            email=user.email,
            display_name=user.display_name,
            active=user.status == UserStatus.ACTIVE,
            tenant_slug=tenant_slug,
            dept_code=dept_code,
            dept_role=dept_role,
            system_role=user.system_role,
        )

    def sync_user_by_id(self, user_id: uuid.UUID) -> ProvisioningResult | None:
        """Load user with dept assignments and sync to Superset."""
        user = self._db.scalar(
            select(User)
            .options(joinedload(User.dept_roles).joinedload(UserDeptRole.department))
            .where(User.id == user_id)
        )
        if user is None:
            return None
        tenant = self._db.get(Tenant, user.tenant_id)
        if tenant is None:
            return None

        dept_code: str | None = None
        dept_role: DeptRole | None = None
        if user.dept_roles:
            assignment = user.dept_roles[0]
            if assignment.department is not None:
                dept_code = assignment.department.code
                dept_role = assignment.role

        return self.sync_user(
            user,
            tenant.slug,
            dept_code=dept_code,
            dept_role=dept_role,
        )

    def reconcile_tenant(self, tenant_id: uuid.UUID) -> list[ProvisioningResult]:
        """Ensure all roles and syncable users exist in Superset."""
        tenant = self._db.get(Tenant, tenant_id)
        if tenant is None or tenant.slug == "platform":
            return []

        results = list(self.provision_tenant_roles(tenant.slug, tenant.id))

        departments = self._db.scalars(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.status == DepartmentStatus.ACTIVE,
            )
        ).all()
        for dept in departments:
            results.extend(
                self.provision_department_roles(tenant.slug, tenant.id, dept.code)
            )

        users = self._db.scalars(
            select(User)
            .options(joinedload(User.dept_roles).joinedload(UserDeptRole.department))
            .where(
                User.tenant_id == tenant_id,
                User.system_role.in_(
                    [
                        SystemRole.CNTT_CHUYENVIEN,
                        SystemRole.CNTT_LANHDAO,
                        SystemRole.DEPT_USER,
                    ]
                ),
            )
        ).unique().all()

        for user in users:
            dept_code = None
            dept_role = None
            if user.dept_roles and user.dept_roles[0].department is not None:
                dept_code = user.dept_roles[0].department.code
                dept_role = user.dept_roles[0].role
            result = self.sync_user(
                user,
                tenant.slug,
                dept_code=dept_code,
                dept_role=dept_role,
            )
            results.append(result)

        return results

    def process_pending_retries(self) -> int:
        """Retry failed provisioning jobs that are due."""
        now = datetime.now(timezone.utc)
        pending = self._db.scalars(
            select(ProvisioningSyncLog).where(
                ProvisioningSyncLog.status == ProvisioningSyncStatus.FAILED,
                ProvisioningSyncLog.next_retry_at.isnot(None),
                ProvisioningSyncLog.next_retry_at <= now,
                ProvisioningSyncLog.attempts < self._settings.provisioning_max_retries,
            )
        ).all()

        retried = 0
        for entry in pending:
            if entry.entity_type == ProvisioningEntityType.ROLE:
                blueprint = blueprint_for_role_name(entry.entity_key)
                if blueprint is None:
                    continue
                self._provision_role(
                    tenant_id=entry.tenant_id,
                    role_name=entry.entity_key,
                    blueprint=blueprint,
                    operation=entry.operation,
                    existing_log=entry,
                )
                retried += 1
            elif entry.entity_type == ProvisioningEntityType.USER:
                user_id = uuid.UUID(entry.entity_key)
                self.sync_user_by_id(user_id)
                retried += 1
        return retried

    def department_provisioning_summary(
        self,
        tenant_slug: str,
        tenant_id: uuid.UUID,
        dept_code: str,
    ) -> ProvisioningResult:
        """Aggregate status for dept CV/LD role sync after department create."""
        role_names = dept_role_names(tenant_slug, dept_code)
        logs = self.get_latest_status(
            tenant_id,
            limit=50,
        )
        role_logs = [log for log in logs if log.entity_key in role_names]
        if not role_logs:
            if not self.enabled:
                return ProvisioningResult(
                    entity_key=dept_code,
                    status=ProvisioningSyncStatus.SKIPPED,
                    message="Superset provisioning not configured",
                )
            return ProvisioningResult(
                entity_key=dept_code,
                status=ProvisioningSyncStatus.PENDING,
                message="Provisioning queued",
            )

        statuses = {log.status for log in role_logs}
        if ProvisioningSyncStatus.FAILED in statuses:
            failed = next(
                log for log in role_logs if log.status == ProvisioningSyncStatus.FAILED
            )
            return ProvisioningResult(
                entity_key=dept_code,
                status=ProvisioningSyncStatus.FAILED,
                message=failed.error_message,
            )
        if ProvisioningSyncStatus.DEAD_LETTER in statuses:
            dead = next(
                log
                for log in role_logs
                if log.status == ProvisioningSyncStatus.DEAD_LETTER
            )
            return ProvisioningResult(
                entity_key=dept_code,
                status=ProvisioningSyncStatus.DEAD_LETTER,
                message=dead.error_message,
            )
        if all(log.status == ProvisioningSyncStatus.SUCCESS for log in role_logs):
            return ProvisioningResult(
                entity_key=dept_code,
                status=ProvisioningSyncStatus.SUCCESS,
                message="Superset roles synced",
            )
        return ProvisioningResult(
            entity_key=dept_code,
            status=ProvisioningSyncStatus.PENDING,
            message="Provisioning in progress",
        )

    def get_latest_status(
        self,
        tenant_id: uuid.UUID,
        *,
        entity_key: str | None = None,
        limit: int = 20,
    ) -> list[ProvisioningSyncLog]:
        stmt = select(ProvisioningSyncLog).where(
            ProvisioningSyncLog.tenant_id == tenant_id
        )
        if entity_key:
            stmt = stmt.where(ProvisioningSyncLog.entity_key == entity_key)
        stmt = stmt.order_by(ProvisioningSyncLog.updated_at.desc()).limit(limit)
        return list(self._db.scalars(stmt).all())

    def _provision_role(
        self,
        *,
        tenant_id: uuid.UUID,
        role_name: str,
        blueprint: RoleBlueprint,
        operation: ProvisioningOperation,
        existing_log: ProvisioningSyncLog | None = None,
    ) -> ProvisioningResult:
        log = existing_log or self._get_or_create_log(
            tenant_id=tenant_id,
            entity_type=ProvisioningEntityType.ROLE,
            entity_key=role_name,
            operation=operation,
        )

        if not self.enabled:
            return self._mark_skipped(log, "Superset provisioning not configured")

        log.attempts += 1
        try:
            role = self._ensure_active_role(role_name)
            if role is None:
                role = self._client.create_role(role_name)

            permission_ids = self._resolve_blueprint_permission_ids(blueprint)
            if permission_ids:
                self._client.set_role_permissions(role.id, permission_ids)

            return self._mark_success(log, role.id)
        except SupersetClientError as exc:
            return self._mark_failure(log, str(exc))

    def _deactivate_role(
        self,
        *,
        tenant_id: uuid.UUID,
        role_name: str,
    ) -> ProvisioningResult:
        log = self._get_or_create_log(
            tenant_id=tenant_id,
            entity_type=ProvisioningEntityType.ROLE,
            entity_key=role_name,
            operation=ProvisioningOperation.DEACTIVATE,
        )

        if not self.enabled:
            return self._mark_skipped(log, "Superset provisioning not configured")

        log.attempts += 1
        try:
            role = self._client.find_role_by_name(role_name)
            if role is None:
                inactive_name = inactive_role_name(role_name)
                role = self._client.find_role_by_name(inactive_name)
                if role is None:
                    return self._mark_success(log, None, message="Role not found in Superset")

            new_name = inactive_role_name(role.name)
            if role.name != new_name:
                self._client.update_role_name(role.id, new_name)

            self._client.set_role_users(role.id, [])
            return self._mark_success(log, role.id, message="Role soft-deactivated")
        except SupersetClientError as exc:
            return self._mark_failure(log, str(exc))

    def _ensure_active_role(self, role_name: str) -> SupersetRole | None:
        """Return role by canonical name, restoring from ``__inactive`` if needed."""
        canonical = active_role_name(role_name)
        role = self._client.find_role_by_name(canonical)
        if role is not None:
            return role

        inactive = self._client.find_role_by_name(inactive_role_name(canonical))
        if inactive is None:
            return None

        self._client.update_role_name(inactive.id, canonical)
        return self._client.find_role_by_name(canonical)

    def _resync_department_users(
        self,
        tenant_slug: str,
        tenant_id: uuid.UUID,
        dept_code: str,
    ) -> list[ProvisioningResult]:
        """Re-attach Superset roles for users still assigned to an active department."""
        department = self._db.scalar(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.code == dept_code,
                Department.status == DepartmentStatus.ACTIVE,
            )
        )
        if department is None:
            return []

        assignments = self._db.scalars(
            select(UserDeptRole)
            .options(joinedload(UserDeptRole.user))
            .where(UserDeptRole.department_id == department.id)
        ).all()

        results: list[ProvisioningResult] = []
        for assignment in assignments:
            user = assignment.user
            if user is None or not portal_user_needs_superset_sync(user):
                continue
            results.append(
                self.sync_user(
                    user,
                    tenant_slug,
                    dept_code=dept_code,
                    dept_role=assignment.role,
                )
            )
        return results

    def _sync_portal_user(
        self,
        *,
        tenant_id: uuid.UUID,
        portal_user_id: uuid.UUID,
        username: str,
        email: str,
        display_name: str,
        active: bool,
        tenant_slug: str,
        dept_code: str | None,
        dept_role: DeptRole | None,
        system_role: SystemRole,
    ) -> ProvisioningResult:
        log = self._get_or_create_log(
            tenant_id=tenant_id,
            entity_type=ProvisioningEntityType.USER,
            entity_key=str(portal_user_id),
            operation=ProvisioningOperation.CREATE,
        )

        if system_role == SystemRole.DEPT_USER and (not dept_code or not dept_role):
            return self._mark_skipped(
                log,
                "dept_user requires department assignment before Superset sync",
            )

        if not self.enabled:
            return self._mark_skipped(log, "Superset provisioning not configured")

        role_names = superset_role_names_for_user(
            tenant_slug,
            system_role,
            dept_code=dept_code,
            dept_role=dept_role,
        )
        if not role_names:
            return self._mark_skipped(log, "No Superset roles mapped for user")

        log.attempts += 1
        try:
            role_ids: list[int] = []
            for role_name in role_names:
                role = self._ensure_active_role(role_name)
                if role is None:
                    raise SupersetClientError(
                        f"Required Superset role '{role_name}' does not exist"
                    )
                role_ids.append(role.id)

            first_name, last_name = split_display_name(display_name)
            existing = self._client.find_user_by_username(username)
            if existing is None:
                created = self._client.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    role_ids=role_ids,
                    active=active,
                )
                return self._mark_success(log, created.id)

            self._client.update_user(
                existing.id,
                email=email,
                first_name=first_name,
                last_name=last_name,
                role_ids=role_ids,
                active=active,
            )
            return self._mark_success(log, existing.id)
        except SupersetClientError as exc:
            return self._mark_failure(log, str(exc))

    def _resolve_blueprint_permission_ids(self, blueprint: RoleBlueprint) -> list[int]:
        permission_map = self._load_permission_names()
        merged: set[int] = set()

        for base_role_name in base_roles_for_blueprint(blueprint):
            base_role = self._client.find_role_by_name(base_role_name)
            if base_role is None:
                logger.warning("Base Superset role '%s' not found", base_role_name)
                continue
            for perm_id in base_role.permission_ids:
                perm_name = permission_map.get(perm_id, "")
                if perm_name and not is_export_permission(perm_name):
                    merged.add(perm_id)

        return sorted(merged)

    def _load_permission_names(self) -> dict[int, str]:
        if self._permission_name_cache is not None:
            return self._permission_name_cache

        mapping: dict[int, str] = {}
        page = 0
        while True:
            results, total = self._client.list_permissions_page(page, PAGE_SIZE)
            if not results:
                break
            for item in results:
                perm = item.get("permission") or {}
                mapping[int(item["id"])] = str(perm.get("name") or "")
            if len(mapping) >= total or len(results) < PAGE_SIZE:
                break
            page += 1

        self._permission_name_cache = mapping
        return mapping

    def _get_or_create_log(
        self,
        *,
        tenant_id: uuid.UUID,
        entity_type: ProvisioningEntityType,
        entity_key: str,
        operation: ProvisioningOperation,
    ) -> ProvisioningSyncLog:
        existing = self._db.scalar(
            select(ProvisioningSyncLog)
            .where(
                ProvisioningSyncLog.tenant_id == tenant_id,
                ProvisioningSyncLog.entity_type == entity_type,
                ProvisioningSyncLog.entity_key == entity_key,
                ProvisioningSyncLog.operation == operation,
            )
            .order_by(ProvisioningSyncLog.created_at.desc())
            .limit(1)
        )
        if existing is not None:
            return existing

        log = ProvisioningSyncLog(
            tenant_id=tenant_id,
            entity_type=entity_type,
            entity_key=entity_key,
            operation=operation,
            status=ProvisioningSyncStatus.PENDING,
        )
        self._db.add(log)
        self._db.flush()
        return log

    def _mark_success(
        self,
        log: ProvisioningSyncLog,
        superset_id: int | None,
        *,
        message: str | None = None,
    ) -> ProvisioningResult:
        log.status = ProvisioningSyncStatus.SUCCESS
        log.superset_id = superset_id
        log.error_message = message
        log.next_retry_at = None
        self._db.commit()
        return ProvisioningResult(
            entity_key=log.entity_key,
            status=ProvisioningSyncStatus.SUCCESS,
            superset_id=superset_id,
            message=message,
        )

    def _mark_skipped(self, log: ProvisioningSyncLog, message: str) -> ProvisioningResult:
        log.status = ProvisioningSyncStatus.SKIPPED
        log.error_message = message
        log.next_retry_at = None
        self._db.commit()
        return ProvisioningResult(
            entity_key=log.entity_key,
            status=ProvisioningSyncStatus.SKIPPED,
            message=message,
        )

    def _mark_failure(self, log: ProvisioningSyncLog, message: str) -> ProvisioningResult:
        log.error_message = message
        if log.attempts >= self._settings.provisioning_max_retries:
            log.status = ProvisioningSyncStatus.DEAD_LETTER
            log.next_retry_at = None
        else:
            log.status = ProvisioningSyncStatus.FAILED
            delay = self._settings.provisioning_retry_delay_seconds
            log.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        self._db.commit()
        return ProvisioningResult(
            entity_key=log.entity_key,
            status=log.status,
            message=message,
        )
