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
"""Export transaction workflow — Phase 10–11."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.auth.policy import (
    Capability,
    has_capability,
    is_dept_leader,
    is_dept_specialist,
)
from app.export.service import export_bytes
from app.export.superset_data import ExportDataError, fetch_template_query_data
from app.models.export_template import ExportTemplate, TemplateStatus
from app.models.export_transaction import ExportTransaction, TransactionStatus
from app.models.tenant import Tenant
from app.models.user import User
from app.templates.access import (
    primary_department_id,
    template_accessible_by_department,
)


class TransactionError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_transaction_or_raise(
    db: Session,
    tenant_id: uuid.UUID,
    transaction_id: uuid.UUID,
) -> ExportTransaction:
    txn = db.scalar(
        select(ExportTransaction).where(
            ExportTransaction.id == transaction_id,
            ExportTransaction.tenant_id == tenant_id,
        )
    )
    if txn is None:
        raise TransactionError("Transaction not found", status_code=404)
    return txn


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
        raise TransactionError("Template not found", status_code=404)
    return template


def _assert_dept_cv(user: User) -> uuid.UUID:
    if not is_dept_specialist(user):
        raise TransactionError("Department specialist access required", status_code=403)
    department_id = primary_department_id(user)
    if department_id is None:
        raise TransactionError("Department assignment required", status_code=403)
    return department_id


def _assert_dept_ld(user: User) -> uuid.UUID:
    if not is_dept_leader(user):
        raise TransactionError("Department leader access required", status_code=403)
    department_id = primary_department_id(user)
    if department_id is None:
        raise TransactionError("Department assignment required", status_code=403)
    return department_id


def transaction_to_dict(
    txn: ExportTransaction,
    *,
    template_name: str | None = None,
    creator_name: str | None = None,
) -> dict[str, Any]:
    return {
        "id": str(txn.id),
        "tenant_id": str(txn.tenant_id),
        "template_id": str(txn.template_id),
        "template_name": template_name,
        "department_id": str(txn.department_id),
        "params_json": txn.params_json or {},
        "status": txn.status.value,
        "reject_comment": txn.reject_comment,
        "request_reason": txn.request_reason,
        "created_by": str(txn.created_by),
        "created_by_name": creator_name,
        "submitted_at": txn.submitted_at.isoformat() if txn.submitted_at else None,
        "approved_by": str(txn.approved_by) if txn.approved_by else None,
        "approved_at": txn.approved_at.isoformat() if txn.approved_at else None,
        "created_at": txn.created_at.isoformat() if txn.created_at else None,
        "updated_at": txn.updated_at.isoformat() if txn.updated_at else None,
    }


def list_my_transactions(db: Session, user: User) -> list[ExportTransaction]:
    if not has_capability(user, Capability.DEPT_TRANSACTIONS):
        raise TransactionError("Insufficient permissions", status_code=403)
    return list(
        db.scalars(
            select(ExportTransaction)
            .where(
                ExportTransaction.tenant_id == user.tenant_id,
                ExportTransaction.created_by == user.id,
            )
            .order_by(ExportTransaction.updated_at.desc())
        ).all()
    )


def list_pending_transactions(db: Session, user: User) -> list[ExportTransaction]:
    department_id = _assert_dept_ld(user)
    return list(
        db.scalars(
            select(ExportTransaction)
            .where(
                ExportTransaction.tenant_id == user.tenant_id,
                ExportTransaction.department_id == department_id,
                ExportTransaction.status == TransactionStatus.SUBMITTED,
            )
            .order_by(ExportTransaction.submitted_at.asc())
        ).all()
    )


def create_transaction(
    db: Session,
    user: User,
    *,
    template_id: uuid.UUID,
    reason: str,
    params_json: dict[str, Any] | None = None,
    ip_address: str | None = None,
) -> ExportTransaction:
    department_id = _assert_dept_cv(user)
    template = _get_template_or_raise(db, user.tenant_id, template_id)
    if template.status != TemplateStatus.PUBLISHED:
        raise TransactionError("Template is not published", status_code=409)
    if not template_accessible_by_department(db, template, department_id):
        raise TransactionError("Template is not shared with your department", status_code=403)

    trimmed_reason = reason.strip()
    if not trimmed_reason:
        raise TransactionError("Export reason is required", status_code=422)

    txn = ExportTransaction(
        tenant_id=user.tenant_id,
        template_id=template.id,
        department_id=department_id,
        params_json=params_json or {},
        request_reason=trimmed_reason,
        status=TransactionStatus.DRAFT,
        created_by=user.id,
    )
    db.add(txn)
    db.commit()
    db.refresh(txn)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="EXPORT_TXN_CREATED",
        entity_type="export_transaction",
        entity_id=str(txn.id),
        actor_id=user.id,
        payload={"template_id": str(template.id), "template_name": template.name, "reason": trimmed_reason},
        ip_address=ip_address,
    )
    return txn


def submit_transaction(
    db: Session,
    user: User,
    transaction_id: uuid.UUID,
    *,
    ip_address: str | None = None,
) -> ExportTransaction:
    department_id = _assert_dept_cv(user)
    txn = _get_transaction_or_raise(db, user.tenant_id, transaction_id)
    if txn.created_by != user.id or txn.department_id != department_id:
        raise TransactionError("Insufficient permissions", status_code=403)
    if txn.status != TransactionStatus.DRAFT:
        raise TransactionError("Only draft transactions can be submitted", status_code=409)
    if not (txn.request_reason or "").strip():
        raise TransactionError("Export reason is required before submission", status_code=422)

    txn.status = TransactionStatus.SUBMITTED
    txn.submitted_at = _now()
    txn.reject_comment = None
    db.commit()
    db.refresh(txn)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="EXPORT_TXN_SUBMITTED",
        entity_type="export_transaction",
        entity_id=str(txn.id),
        actor_id=user.id,
        ip_address=ip_address,
    )
    return txn


def approve_transaction(
    db: Session,
    user: User,
    transaction_id: uuid.UUID,
    *,
    ip_address: str | None = None,
) -> ExportTransaction:
    department_id = _assert_dept_ld(user)
    txn = _get_transaction_or_raise(db, user.tenant_id, transaction_id)
    if txn.department_id != department_id:
        raise TransactionError("Transaction belongs to another department", status_code=403)
    if txn.status != TransactionStatus.SUBMITTED:
        raise TransactionError("Only submitted transactions can be approved", status_code=409)

    txn.status = TransactionStatus.APPROVED
    txn.approved_by = user.id
    txn.approved_at = _now()
    txn.reject_comment = None
    db.commit()
    db.refresh(txn)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="EXPORT_TXN_APPROVED",
        entity_type="export_transaction",
        entity_id=str(txn.id),
        actor_id=user.id,
        ip_address=ip_address,
    )
    return txn


def reject_transaction(
    db: Session,
    user: User,
    transaction_id: uuid.UUID,
    *,
    comment: str,
    ip_address: str | None = None,
) -> ExportTransaction:
    department_id = _assert_dept_ld(user)
    txn = _get_transaction_or_raise(db, user.tenant_id, transaction_id)
    if txn.department_id != department_id:
        raise TransactionError("Transaction belongs to another department", status_code=403)
    if txn.status != TransactionStatus.SUBMITTED:
        raise TransactionError("Only submitted transactions can be rejected", status_code=409)

    trimmed = comment.strip()
    if not trimmed:
        raise TransactionError("Rejection comment is required", status_code=422)

    txn.status = TransactionStatus.REJECTED
    txn.reject_comment = trimmed
    txn.approved_by = None
    txn.approved_at = None
    db.commit()
    db.refresh(txn)

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="EXPORT_TXN_REJECTED",
        entity_type="export_transaction",
        entity_id=str(txn.id),
        actor_id=user.id,
        payload={"comment": trimmed},
        ip_address=ip_address,
    )
    return txn


def _load_tenant_or_raise(db: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise TransactionError("Tenant not found", status_code=404)
    return tenant


def _fetch_transaction_data(
    db: Session,
    user: User,
    template: ExportTemplate,
) -> dict[str, Any]:
    tenant = _load_tenant_or_raise(db, user.tenant_id)
    try:
        return fetch_template_query_data(user=user, tenant=tenant, template=template)
    except ExportDataError as exc:
        raise TransactionError(exc.message, status_code=exc.status_code) from exc


def preview_transaction(
    db: Session,
    user: User,
    transaction_id: uuid.UUID,
) -> dict[str, Any]:
    txn = _get_transaction_or_raise(db, user.tenant_id, transaction_id)
    _assert_can_access_transaction(user, txn)

    template = _get_template_or_raise(db, user.tenant_id, txn.template_id)
    return _fetch_transaction_data(db, user, template)


def download_transaction_export(
    db: Session,
    user: User,
    transaction_id: uuid.UUID,
    *,
    export_format: str,
    ip_address: str | None = None,
) -> tuple[bytes, str, str]:
    """Return bytes, media type, and file extension for an approved transaction."""
    txn = _get_transaction_or_raise(db, user.tenant_id, transaction_id)
    _assert_can_download(user, txn)

    if txn.status not in (TransactionStatus.APPROVED, TransactionStatus.DOWNLOADED):
        raise TransactionError(
            "Download is available only after leader approval",
            status_code=409,
        )

    template = _get_template_or_raise(db, user.tenant_id, txn.template_id)
    preview = _fetch_transaction_data(db, user, template)
    file_bytes, media_type, extension = export_bytes(
        columns=preview["columns"],
        rows=preview["rows"],
        export_format=export_format,
        title=template.name,
    )

    if txn.status == TransactionStatus.APPROVED:
        txn.status = TransactionStatus.DOWNLOADED
        db.commit()

    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="EXPORT_TXN_DOWNLOAD",
        entity_type="export_transaction",
        entity_id=str(txn.id),
        actor_id=user.id,
        payload={"format": export_format, "template_name": template.name},
        ip_address=ip_address,
    )
    return file_bytes, media_type, extension


def _assert_can_access_transaction(user: User, txn: ExportTransaction) -> None:
    if is_dept_leader(user) and primary_department_id(user) == txn.department_id:
        return
    if is_dept_specialist(user) and txn.created_by == user.id:
        return
    raise TransactionError("Insufficient permissions", status_code=403)


def _assert_can_download(user: User, txn: ExportTransaction) -> None:
    if txn.status not in (TransactionStatus.APPROVED, TransactionStatus.DOWNLOADED):
        raise TransactionError("Transaction is not approved", status_code=409)
    if is_dept_leader(user) and primary_department_id(user) == txn.department_id:
        return
    if is_dept_specialist(user) and txn.created_by == user.id:
        return
    raise TransactionError("Insufficient permissions", status_code=403)
