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
"""Superset publish helpers for export templates — Phase 8."""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

from app.config import Settings
from app.models.department import Department
from app.models.export_template import TemplateShareMode
from app.provisioning.blueprint import (
    cntt_ld_role_name,
    dept_cv_role_name,
    dept_ld_role_name,
)
from app.provisioning.superset_client import SupersetClient, SupersetClientError

logger = logging.getLogger(__name__)

_DATASET_NAME_MAX = 250


@dataclass(frozen=True)
class PushDatasetResult:
    dataset_id: int | None
    message: str | None = None


@dataclass(frozen=True)
class SyncDashboardResult:
    dashboard_id: int | None
    dashboard_title: str | None = None
    message: str | None = None


def _slugify_dataset_name(template_name: str, template_id: uuid.UUID) -> str:
    base = re.sub(r"[^a-zA-Z0-9_]+", "_", template_name.strip())[:80].strip("_")
    if not base:
        base = "portal_template"
    suffix = str(template_id).split("-")[0]
    name = f"portal_{base}_{suffix}"
    return name[:_DATASET_NAME_MAX]


def _pseudo_id(seed: str) -> int:
    digest = hashlib.sha256(seed.encode()).hexdigest()
    return int(digest[:8], 16) % 900_000 + 100_000


def push_sql_to_superset(
    *,
    client: SupersetClient,
    settings: Settings,
    template_id: uuid.UUID,
    template_name: str,
    sql: str,
) -> PushDatasetResult:
    """Create a virtual dataset on Superset from the template SQL."""
    if not client.enabled:
        pseudo = _pseudo_id(f"{template_id}:{sql}")
        return PushDatasetResult(
            dataset_id=pseudo,
            message="Superset service account not configured — using placeholder ID",
        )

    try:
        if not client.health_check():
            raise SupersetClientError("Superset health check failed")
        dataset_name = _slugify_dataset_name(template_name, template_id)
        existing_id = client.find_dataset_id_by_table_name(dataset_name)
        if existing_id is not None:
            client.update_virtual_dataset_sql(existing_id, sql=sql)
            return PushDatasetResult(dataset_id=existing_id, message="Updated existing dataset SQL")
        dataset_id = client.create_virtual_dataset(
            database_id=settings.superset_template_database_id,
            table_name=dataset_name,
            sql=sql,
        )
        return PushDatasetResult(dataset_id=dataset_id)
    except SupersetClientError as exc:
        if "already exists" in exc.message.lower():
            existing_id = client.find_dataset_id_by_table_name(
                _slugify_dataset_name(template_name, template_id)
            )
            if existing_id is not None:
                client.update_virtual_dataset_sql(existing_id, sql=sql)
                return PushDatasetResult(
                    dataset_id=existing_id,
                    message="Linked existing dataset and refreshed SQL",
                )
        logger.warning("Superset dataset push failed: %s", exc)
        raise


def sync_dashboard_from_superset(
    *,
    client: SupersetClient,
    tenant_slug: str,
    portal_username: str,
    portal_email: str | None,
    template_name: str,
    dataset_id: int | None,
) -> SyncDashboardResult:
    """
    Find a dashboard created for this template.

    1. Dashboards owned by the designer's Superset account
    2. Dashboards that include charts from the template dataset (fallback)
    """
    if not client.enabled:
        pseudo = _pseudo_id(f"{tenant_slug}:{portal_username}:{template_name}")
        return SyncDashboardResult(
            dashboard_id=pseudo,
            dashboard_title=template_name,
            message="Superset service account not configured — using placeholder ID",
        )

    try:
        ss_user = client.resolve_portal_user(
            tenant_slug,
            portal_username=portal_username,
            email=portal_email,
        )

        dashboards: list[dict[str, Any]] = []
        if ss_user is not None:
            dashboards = client.list_dashboards_for_owner(ss_user.id)

        if not dashboards and dataset_id is not None:
            dashboards = client.find_dashboards_by_dataset_id(dataset_id)

        if not dashboards:
            return SyncDashboardResult(
                dashboard_id=None,
                message="No dashboard found — create one in Superset first",
            )

        normalized_name = template_name.strip().lower()
        title_match = next(
            (
                item
                for item in dashboards
                if str(item.get("dashboard_title") or "").strip().lower()
                == normalized_name
            ),
            None,
        )
        chosen = title_match or dashboards[0]
        dashboard_id = int(chosen["id"])
        title = str(chosen.get("dashboard_title") or template_name)
        return SyncDashboardResult(dashboard_id=dashboard_id, dashboard_title=title)
    except SupersetClientError as exc:
        logger.warning("Superset dashboard sync failed: %s", exc)
        raise


def grant_reviewer_access(
    *,
    client: SupersetClient,
    tenant_slug: str,
    dashboard_id: int,
) -> str | None:
    """Publish dashboard for CNTT approvers only (DASHBOARD_RBAC)."""
    if not client.enabled:
        return "Superset not configured — skipped reviewer RBAC"

    try:
        role_ids = client.find_role_ids_by_names([cntt_ld_role_name(tenant_slug)])
        if not role_ids:
            raise SupersetClientError("CNTT approver role not found in Superset")
        client.update_dashboard_rbac(
            dashboard_id,
            published=True,
            role_ids=role_ids,
        )
        return None
    except SupersetClientError as exc:
        logger.warning("Reviewer RBAC update failed: %s", exc)
        return str(exc)


def grant_department_access(
    *,
    client: SupersetClient,
    tenant_slug: str,
    dashboard_id: int,
    share_mode: TemplateShareMode,
    departments: list[Department],
) -> str | None:
    """Extend dashboard RBAC to selected or all active departments."""
    if not client.enabled:
        return "Superset not configured — skipped department RBAC"

    dept_codes = [dept.code for dept in departments]
    if share_mode == TemplateShareMode.ALL:
        role_names = [
            name
            for code in dept_codes
            for name in (
                dept_cv_role_name(tenant_slug, code),
                dept_ld_role_name(tenant_slug, code),
            )
        ]
    else:
        role_names = [
            name
            for code in dept_codes
            for name in (
                dept_cv_role_name(tenant_slug, code),
                dept_ld_role_name(tenant_slug, code),
            )
        ]

    try:
        reviewer_role = cntt_ld_role_name(tenant_slug)
        role_names.append(reviewer_role)
        role_ids = client.find_role_ids_by_names(role_names)
        if not role_ids:
            raise SupersetClientError("No department roles resolved in Superset")
        client.update_dashboard_rbac(
            dashboard_id,
            published=True,
            role_ids=role_ids,
        )
        return None
    except SupersetClientError as exc:
        logger.warning("Department RBAC update failed: %s", exc)
        return str(exc)
