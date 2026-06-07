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

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.sql_validator import validate_read_only_sql
from app.audit.service import write_audit_log
from app.auth.policy import Capability, has_capability
from app.config import get_settings
from app.models.export_template import ExportTemplate, TemplateStatus
from app.models.tenant import TenantSettings
from app.models.user import SystemRole, User
from app.provisioning.superset_client import SupersetClient
from app.templates.preview import preview_sql
from app.templates.publish import publish_template_to_superset


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


def template_to_dict(template: ExportTemplate, *, creator_name: str | None = None) -> dict[str, Any]:
    return {
        "id": str(template.id),
        "tenant_id": str(template.tenant_id),
        "name": template.name,
        "description": template.description,
        "sql_snapshot": template.sql_snapshot,
        "status": template.status.value,
        "share_mode": template.share_mode.value if template.share_mode else None,
        "share_scope_version": template.share_scope_version or 0,
        "reject_comment": template.reject_comment,
        "created_by": str(template.created_by),
        "created_by_name": creator_name,
        "published_by": str(template.published_by) if template.published_by else None,
        "superset_dashboard_id": template.superset_dashboard_id,
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


def _assert_can_view(user: User, template: ExportTemplate) -> None:
    if not has_capability(user, Capability.CNTT_TEMPLATES):
        raise TemplateError("Insufficient permissions", status_code=403)
    if has_capability(user, Capability.CNTT_APPROVALS):
        return
    if template.created_by != user.id:
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
    _assert_can_view(user, template)
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
    ip_address: str | None = None,
) -> ExportTemplate:
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    _assert_creator(user, template)
    if template.status != TemplateStatus.DRAFT:
        raise TemplateError("Only draft templates can be submitted", status_code=409)
    if not template.sql_snapshot.strip():
        raise TemplateError("SQL is required before submit", status_code=422)
    _validate_sql_or_raise(template.sql_snapshot)

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
        payload={"name": template.name},
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
    settings: TenantSettings,
    ip_address: str | None = None,
    signature_payload_hash: str | None = None,
    signer_cert_serial: str | None = None,
) -> ExportTemplate:
    _assert_approver(user)
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    if template.status != TemplateStatus.REVIEW:
        raise TemplateError("Only templates in review can be approved", status_code=409)

    pki_config = settings.pki_config or {}
    if settings.digital_signature_enabled and pki_config.get("require_cert_at_approval"):
        if not signature_payload_hash or not signer_cert_serial:
            raise TemplateError(
                "Digital signature required for template approval",
                status_code=403,
            )

    client = SupersetClient(get_settings())
    publish_result = publish_template_to_superset(
        client=client,
        template_name=template.name,
        sql=template.sql_snapshot,
    )

    now = _now()
    template.status = TemplateStatus.PUBLISHED
    template.published_by = user.id
    template.published_at = now
    template.reject_comment = None
    template.superset_dashboard_id = publish_result.dashboard_id
    template.superset_dataset_id = publish_result.dataset_id
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
            "dashboard_id": publish_result.dashboard_id,
            "dataset_id": publish_result.dataset_id,
            "message": publish_result.message,
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
    _assert_can_view(user, template)

    sql = (sql_override or template.sql_snapshot).strip()
    if not sql:
        raise TemplateError("SQL is required for preview", status_code=422)

    try:
        return preview_sql(sql)
    except ValueError as exc:
        raise TemplateError(str(exc), status_code=422) from exc
