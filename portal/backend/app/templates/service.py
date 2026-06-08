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
"""Export template workflow service — Phase 8."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.ai.sql_validator import validate_read_only_sql
from app.audit.service import write_audit_log
from app.auth.policy import Capability, has_capability
from app.config import get_settings
from app.models.export_template import ExportTemplate, TemplateShareMode, TemplateStatus
from app.models.export_transaction import ExportTransaction
from app.models.tenant import Tenant, TenantSettings
from app.models.user import SystemRole, User
from app.provisioning.superset_client import SupersetClient, SupersetClientError
from app.superset.launch import SupersetLaunchTarget
from app.superset.launch_auth import build_launch_redirect_url
from app.templates.preview import preview_sql
from app.templates.publish import (
    grant_department_access,
    grant_reviewer_access,
    push_sql_to_superset,
    sync_dashboard_from_superset,
)
from app.templates.access import (
    primary_department_id,
    shared_department_rows,
    template_accessible_by_department,
)
from app.templates.share import ShareError, replace_template_shares, resolve_share_departments


class TemplateError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class TemplateListFilters:
    status: TemplateStatus | None = None
    pending_only: bool = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def template_to_dict(
    template: ExportTemplate,
    *,
    creator_name: str | None = None,
    shared_departments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(template.id),
        "tenant_id": str(template.tenant_id),
        "name": template.name,
        "description": template.description,
        "sql_snapshot": template.sql_snapshot,
        "status": template.status.value,
        "share_mode": template.share_mode.value if template.share_mode else None,
        "share_scope_version": template.share_scope_version or 0,
        "shared_departments": shared_departments or [],
        "reject_comment": template.reject_comment,
        "created_by": str(template.created_by),
        "created_by_name": creator_name,
        "published_by": str(template.published_by) if template.published_by else None,
        "superset_dashboard_id": template.superset_dashboard_id,
        "superset_dashboard_title": template.superset_dashboard_title,
        "superset_dataset_id": template.superset_dataset_id,
        "submitted_at": template.submitted_at.isoformat() if template.submitted_at else None,
        "published_at": template.published_at.isoformat() if template.published_at else None,
        "created_at": template.created_at.isoformat() if template.created_at else None,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def _get_template_or_raise(
    db: Session,
    tenant_id: uuid.UUID,
    template_id: uuid.UUID,
) -> ExportTemplate:
    template = db.scalar(
        select(ExportTemplate).where(
            ExportTemplate.id == template_id,
            ExportTemplate.tenant_id == tenant_id,
        )
    )
    if template is None:
        raise TemplateError("Template not found", status_code=404)
    return template


def _assert_can_view(
    db: Session,
    user: User,
    template: ExportTemplate,
) -> None:
    if has_capability(user, Capability.CNTT_APPROVALS):
        return
    if has_capability(user, Capability.CNTT_TEMPLATES):
        if template.created_by == user.id:
            return
        raise TemplateError("Insufficient permissions", status_code=403)
    if has_capability(user, Capability.DEPT_TEMPLATES):
        if template.status != TemplateStatus.PUBLISHED:
            raise TemplateError("Insufficient permissions", status_code=403)
        department_id = primary_department_id(user)
        if department_id is None or not template_accessible_by_department(
            db, template, department_id
        ):
            raise TemplateError(
                "Template is not shared with your department",
                status_code=403,
            )
        return
    raise TemplateError("Insufficient permissions", status_code=403)


def _assert_creator(user: User, template: ExportTemplate) -> None:
    if template.created_by != user.id:
        raise TemplateError("Only the template author may perform this action", status_code=403)
    if user.system_role != SystemRole.CNTT_CHUYENVIEN:
        raise TemplateError("Template designer access required", status_code=403)


def _assert_approver(user: User) -> None:
    if not has_capability(user, Capability.CNTT_APPROVALS):
        raise TemplateError("Template approver access required", status_code=403)


def _validate_sql_or_raise(sql: str) -> None:
    validation = validate_read_only_sql(sql)
    if not validation.valid:
        raise TemplateError(validation.reason or "Invalid SQL", status_code=422)


def list_templates(
    db: Session,
    user: User,
    *,
    filters: TemplateListFilters | None = None,
) -> list[ExportTemplate]:
    if not has_capability(user, Capability.CNTT_TEMPLATES):
        raise TemplateError("Insufficient permissions", status_code=403)

    query = select(ExportTemplate).where(ExportTemplate.tenant_id == user.tenant_id)
    filters = filters or TemplateListFilters()

    if filters.pending_only:
        if not has_capability(user, Capability.CNTT_APPROVALS):
            raise TemplateError("Template approver access required", status_code=403)
        query = query.where(ExportTemplate.status == TemplateStatus.REVIEW)
    elif not has_capability(user, Capability.CNTT_APPROVALS):
        query = query.where(ExportTemplate.created_by == user.id)

    if filters.status is not None:
        query = query.where(ExportTemplate.status == filters.status)

    query = query.order_by(ExportTemplate.updated_at.desc())
    return list(db.scalars(query).all())


def get_template(db: Session, user: User, template_id: uuid.UUID) -> ExportTemplate:
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    _assert_can_view(db, user, template)
    return template


def create_template(
    db: Session,
    user: User,
    *,
    name: str,
    description: str | None,
    sql_snapshot: str,
    ip_address: str | None = None,
) -> ExportTemplate:
    if user.system_role != SystemRole.CNTT_CHUYENVIEN:
        raise TemplateError("Template designer access required", status_code=403)

    trimmed_name = name.strip()
    if not trimmed_name:
        raise TemplateError("Template name is required", status_code=422)

    sql = sql_snapshot.strip()
    if sql:
        _validate_sql_or_raise(sql)

    template = ExportTemplate(
        tenant_id=user.tenant_id,
        name=trimmed_name,
        description=description.strip() if description else None,
        sql_snapshot=sql,
        status=TemplateStatus.DRAFT,
        created_by=user.id,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="TEMPLATE_CREATED",
        entity_type="export_template",
        entity_id=str(template.id),
        actor_id=user.id,
        payload={"name": template.name},
        ip_address=ip_address,
    )
    return template


def update_template(
    db: Session,
    user: User,
    template_id: uuid.UUID,
    *,
    name: str | None = None,
    description: str | None = None,
    sql_snapshot: str | None = None,
    ip_address: str | None = None,
) -> ExportTemplate:
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    _assert_creator(user, template)
    if template.status != TemplateStatus.DRAFT:
        raise TemplateError("Only draft templates can be edited", status_code=409)

    if name is not None:
        trimmed = name.strip()
        if not trimmed:
            raise TemplateError("Template name is required", status_code=422)
        template.name = trimmed

    if description is not None:
        template.description = description.strip() or None

    if sql_snapshot is not None:
        sql = sql_snapshot.strip()
        if not sql:
            raise TemplateError("SQL is required", status_code=422)
        _validate_sql_or_raise(sql)
        template.sql_snapshot = sql

    template.reject_comment = None
    db.commit()
    db.refresh(template)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="TEMPLATE_UPDATED",
        entity_type="export_template",
        entity_id=str(template.id),
        actor_id=user.id,
        payload={"name": template.name},
        ip_address=ip_address,
    )
    return template


def submit_template(
    db: Session,
    user: User,
    template_id: uuid.UUID,
    *,
    tenant: Tenant,
    ip_address: str | None = None,
) -> ExportTemplate:
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    _assert_creator(user, template)
    if template.status != TemplateStatus.DRAFT:
        raise TemplateError("Only draft templates can be submitted", status_code=409)
    if not template.sql_snapshot.strip():
        raise TemplateError("SQL is required before submit", status_code=422)
    if template.superset_dataset_id is None:
        raise TemplateError(
            "Push SQL to Superset to create a dataset before submitting",
            status_code=409,
        )
    if template.superset_dashboard_id is None:
        raise TemplateError(
            "Link a Superset dashboard before submitting — sync from Superset",
            status_code=409,
        )
    _validate_sql_or_raise(template.sql_snapshot)

    client = SupersetClient(get_settings())
    rbac_message = grant_reviewer_access(
        client=client,
        tenant_slug=tenant.slug,
        dashboard_id=template.superset_dashboard_id,
    )

    template.status = TemplateStatus.REVIEW
    template.submitted_at = _now()
    template.reject_comment = None
    db.commit()
    db.refresh(template)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="TEMPLATE_SUBMIT",
        entity_type="export_template",
        entity_id=str(template.id),
        actor_id=user.id,
        payload={
            "name": template.name,
            "dashboard_id": template.superset_dashboard_id,
            "rbac_message": rbac_message,
        },
        ip_address=ip_address,
    )
    return template


def reject_template(
    db: Session,
    user: User,
    template_id: uuid.UUID,
    *,
    comment: str,
    ip_address: str | None = None,
) -> ExportTemplate:
    _assert_approver(user)
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    if template.status != TemplateStatus.REVIEW:
        raise TemplateError("Only templates in review can be rejected", status_code=409)

    trimmed = comment.strip()
    if not trimmed:
        raise TemplateError("Reject comment is required", status_code=422)

    template.status = TemplateStatus.DRAFT
    template.reject_comment = trimmed
    template.submitted_at = None
    db.commit()
    db.refresh(template)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="TEMPLATE_REJECT",
        entity_type="export_template",
        entity_id=str(template.id),
        actor_id=user.id,
        payload={"comment": trimmed, "name": template.name},
        ip_address=ip_address,
    )
    return template


def approve_template(
    db: Session,
    user: User,
    template_id: uuid.UUID,
    *,
    tenant: Tenant,
    settings: TenantSettings,
    share_mode: TemplateShareMode,
    department_ids: list[uuid.UUID] | None = None,
    ip_address: str | None = None,
    signature_payload_hash: str | None = None,
    signer_cert_serial: str | None = None,
) -> ExportTemplate:
    _assert_approver(user)
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    if template.status != TemplateStatus.REVIEW:
        raise TemplateError("Only templates in review can be approved", status_code=409)
    if template.superset_dashboard_id is None:
        raise TemplateError("Template has no linked Superset dashboard", status_code=409)

    pki_config = settings.pki_config or {}
    if settings.digital_signature_enabled and pki_config.get("require_cert_at_approval"):
        if not signature_payload_hash or not signer_cert_serial:
            raise TemplateError(
                "Digital signature required for template approval",
                status_code=403,
            )

    try:
        departments = resolve_share_departments(
            db,
            user.tenant_id,
            share_mode=share_mode,
            department_ids=department_ids,
        )
    except ShareError as exc:
        raise TemplateError(exc.message, status_code=exc.status_code) from exc

    client = SupersetClient(get_settings())
    rbac_message = grant_department_access(
        client=client,
        tenant_slug=tenant.slug,
        dashboard_id=template.superset_dashboard_id,
        share_mode=share_mode,
        departments=departments,
    )

    now = _now()
    template.status = TemplateStatus.PUBLISHED
    template.published_by = user.id
    template.published_at = now
    template.reject_comment = None
    replace_template_shares(
        db,
        template,
        share_mode=share_mode,
        departments=departments,
        shared_by=user.id,
    )
    db.commit()
    db.refresh(template)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="TEMPLATE_PUBLISH",
        entity_type="export_template",
        entity_id=str(template.id),
        actor_id=user.id,
        payload={
            "name": template.name,
            "dashboard_id": template.superset_dashboard_id,
            "dataset_id": template.superset_dataset_id,
            "share_mode": share_mode.value,
            "department_count": len(departments),
            "rbac_message": rbac_message,
            "signature_payload_hash": signature_payload_hash,
            "signer_cert_serial": signer_cert_serial,
        },
        ip_address=ip_address,
    )
    return template


def preview_template_sql(
    db: Session,
    user: User,
    template_id: uuid.UUID,
    *,
    sql_override: str | None = None,
) -> dict[str, Any]:
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    _assert_can_view(db, user, template)

    sql = (sql_override or template.sql_snapshot).strip()
    if not sql:
        raise TemplateError("SQL is required for preview", status_code=422)

    try:
        return preview_sql(sql)
    except ValueError as exc:
        raise TemplateError(str(exc), status_code=422) from exc


def push_template_dataset(
    db: Session,
    user: User,
    template_id: uuid.UUID,
    *,
    ip_address: str | None = None,
) -> ExportTemplate:
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    _assert_creator(user, template)
    if template.status != TemplateStatus.DRAFT:
        raise TemplateError("Only draft templates can push SQL to Superset", status_code=409)
    if not template.sql_snapshot.strip():
        raise TemplateError("SQL is required before pushing to Superset", status_code=422)
    _validate_sql_or_raise(template.sql_snapshot)

    settings = get_settings()
    client = SupersetClient(settings)
    try:
        result = push_sql_to_superset(
            client=client,
            settings=settings,
            template_id=template.id,
            template_name=template.name,
            sql=template.sql_snapshot,
        )
    except SupersetClientError as exc:
        raise TemplateError(
            f"Failed to create dataset on Superset: {exc.message}",
            status_code=502,
        ) from exc
    template.superset_dataset_id = result.dataset_id
    db.commit()
    db.refresh(template)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="TEMPLATE_PUSH_DATASET",
        entity_type="export_template",
        entity_id=str(template.id),
        actor_id=user.id,
        payload={
            "name": template.name,
            "dataset_id": result.dataset_id,
            "message": result.message,
        },
        ip_address=ip_address,
    )
    return template


def sync_template_dashboard(
    db: Session,
    user: User,
    template_id: uuid.UUID,
    *,
    tenant: Tenant,
    ip_address: str | None = None,
) -> ExportTemplate:
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    _assert_creator(user, template)
    if template.status != TemplateStatus.DRAFT:
        raise TemplateError("Only draft templates can sync dashboard", status_code=409)

    creator = db.get(User, template.created_by)
    if creator is None:
        raise TemplateError("Template author not found", status_code=404)

    client = SupersetClient(get_settings())
    try:
        result = sync_dashboard_from_superset(
            client=client,
            tenant_slug=tenant.slug,
            portal_username=creator.username,
            portal_email=creator.email,
            template_name=template.name,
            dataset_id=template.superset_dataset_id,
        )
    except SupersetClientError as exc:
        raise TemplateError(
            f"Failed to sync dashboard from Superset: {exc.message}",
            status_code=502,
        ) from exc

    if result.dashboard_id is None:
        raise TemplateError(
            result.message or "No Superset dashboard found for this template",
            status_code=404,
        )

    template.superset_dashboard_id = result.dashboard_id
    template.superset_dashboard_title = result.dashboard_title
    db.commit()
    db.refresh(template)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="TEMPLATE_SYNC_DASHBOARD",
        entity_type="export_template",
        entity_id=str(template.id),
        actor_id=user.id,
        payload={
            "name": template.name,
            "dashboard_id": result.dashboard_id,
            "dashboard_title": result.dashboard_title,
            "message": result.message,
        },
        ip_address=ip_address,
    )
    return template


def delete_template(
    db: Session,
    user: User,
    template_id: uuid.UUID,
    *,
    ip_address: str | None = None,
) -> None:
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    _assert_creator(user, template)
    if template.status != TemplateStatus.DRAFT:
        raise TemplateError("Only draft templates can be deleted", status_code=409)

    txn_count = db.scalar(
        select(func.count())
        .select_from(ExportTransaction)
        .where(ExportTransaction.template_id == template.id)
    )
    if txn_count:
        raise TemplateError(
            "Template has export transactions and cannot be deleted",
            status_code=409,
        )

    template_name = template.name
    template_id_str = str(template.id)
    db.delete(template)
    db.commit()

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="TEMPLATE_DELETED",
        entity_type="export_template",
        entity_id=template_id_str,
        actor_id=user.id,
        payload={"name": template_name},
        ip_address=ip_address,
    )


def get_template_launch_url(
    db: Session,
    user: User,
    template_id: uuid.UUID,
    *,
    tenant: Tenant,
    target: SupersetLaunchTarget,
) -> str:
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    _assert_can_view(db, user, template)

    if target == SupersetLaunchTarget.DATASET:
        if template.superset_dataset_id is None:
            raise TemplateError("Dataset not pushed to Superset yet", status_code=409)
        resource_id = template.superset_dataset_id
        if template.created_by != user.id:
            raise TemplateError("Only the template author may open design mode", status_code=403)
        if template.status != TemplateStatus.DRAFT:
            raise TemplateError("Design mode is only available for draft templates", status_code=409)
    elif target == SupersetLaunchTarget.DASHBOARD_VIEW:
        if template.superset_dashboard_id is None:
            raise TemplateError("No Superset dashboard linked to this template", status_code=409)
        resource_id = template.superset_dashboard_id
        if template.created_by != user.id and not has_capability(user, Capability.CNTT_APPROVALS):
            if not (
                has_capability(user, Capability.DEPT_TEMPLATES)
                and template.status == TemplateStatus.PUBLISHED
            ):
                raise TemplateError("Insufficient permissions to view dashboard", status_code=403)
            department_id = primary_department_id(user)
            if department_id is None or not template_accessible_by_department(
                db, template, department_id
            ):
                raise TemplateError(
                    "Template is not shared with your department",
                    status_code=403,
                )
    elif target == SupersetLaunchTarget.DASHBOARD_DESIGN:
        if template.superset_dashboard_id is None:
            raise TemplateError("No Superset dashboard linked to this template", status_code=409)
        resource_id = template.superset_dashboard_id
        if template.created_by != user.id:
            raise TemplateError("Only the template author may open design mode", status_code=403)
        if template.status != TemplateStatus.DRAFT:
            raise TemplateError("Design mode is only available for draft templates", status_code=409)
    else:
        if template.superset_dashboard_id is None:
            raise TemplateError("No Superset dashboard linked to this template", status_code=409)
        resource_id = template.superset_dashboard_id

    if target == SupersetLaunchTarget.DASHBOARD_REVIEW:
        if not has_capability(user, Capability.CNTT_APPROVALS):
            raise TemplateError("Template approver access required", status_code=403)
        if template.status != TemplateStatus.REVIEW:
            raise TemplateError("Review mode requires template in review status", status_code=409)

    return build_launch_redirect_url(
        user=user,
        tenant=tenant,
        target=target,
        resource_id=resource_id,
    )
