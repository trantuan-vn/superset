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
"""Export transaction API — Phase 10–11."""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    CreateTransactionRequest,
    RejectTransactionRequest,
    TemplatePreviewResponse,
    TransactionResponse,
)
from app.auth.dependencies import (
    get_current_user_with_dept_roles,
    require_capability,
)
from app.auth.policy import Capability
from app.db import get_db
from app.models.user import User
from app.transactions.service import (
    TransactionError,
    approve_transaction,
    create_transaction,
    download_transaction_export,
    list_my_transactions,
    list_pending_transactions,
    preview_transaction,
    reject_transaction,
    submit_transaction,
    transaction_to_dict,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _handle_error(exc: TransactionError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _creator_names(db: Session, txns: list) -> dict[uuid.UUID, str]:
    creator_ids = {txn.created_by for txn in txns}
    if not creator_ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(creator_ids))).all()
    return {user.id: user.display_name for user in users}


def _template_names(db: Session, txns: list) -> dict[uuid.UUID, str]:
    from app.models.export_template import ExportTemplate

    template_ids = {txn.template_id for txn in txns}
    if not template_ids:
        return {}
    templates = db.scalars(
        select(ExportTemplate).where(ExportTemplate.id.in_(template_ids))
    ).all()
    return {template.id: template.name for template in templates}


def _to_response(
    db: Session,
    txn,
    *,
    creator_names: dict[uuid.UUID, str] | None = None,
    template_names: dict[uuid.UUID, str] | None = None,
) -> TransactionResponse:
    creators = creator_names or {}
    templates = template_names or {}
    return TransactionResponse(
        **transaction_to_dict(
            txn,
            template_name=templates.get(txn.template_id),
            creator_name=creators.get(txn.created_by),
        )
    )


@router.get("", response_model=list[TransactionResponse])
def list_my_transactions_api(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> list[TransactionResponse]:
    try:
        txns = list_my_transactions(db, user)
    except TransactionError as exc:
        raise _handle_error(exc) from exc
    creators = _creator_names(db, txns)
    templates = _template_names(db, txns)
    return [_to_response(db, txn, creator_names=creators, template_names=templates) for txn in txns]


@router.get("/pending", response_model=list[TransactionResponse])
def list_pending_transactions_api(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_capability(Capability.DEPT_APPROVALS))],
) -> list[TransactionResponse]:
    try:
        txns = list_pending_transactions(db, user)
    except TransactionError as exc:
        raise _handle_error(exc) from exc
    creators = _creator_names(db, txns)
    templates = _template_names(db, txns)
    return [_to_response(db, txn, creator_names=creators, template_names=templates) for txn in txns]


@router.post("", response_model=TransactionResponse, status_code=201)
def create_transaction_api(
    body: CreateTransactionRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_capability(Capability.DEPT_TRANSACTIONS))],
) -> TransactionResponse:
    try:
        template_id = uuid.UUID(body.template_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid template id") from exc
    try:
        txn = create_transaction(
            db,
            user,
            template_id=template_id,
            reason=body.reason,
            params_json=body.params_json,
            ip_address=_client_ip(request),
        )
    except TransactionError as exc:
        raise _handle_error(exc) from exc
    return _to_response(db, txn, template_names=_template_names(db, [txn]))


@router.post("/{transaction_id}/submit", response_model=TransactionResponse)
def submit_transaction_api(
    transaction_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_capability(Capability.DEPT_TRANSACTIONS))],
) -> TransactionResponse:
    try:
        txn = submit_transaction(
            db,
            user,
            transaction_id,
            ip_address=_client_ip(request),
        )
    except TransactionError as exc:
        raise _handle_error(exc) from exc
    return _to_response(db, txn, template_names=_template_names(db, [txn]))


@router.post("/{transaction_id}/approve", response_model=TransactionResponse)
def approve_transaction_api(
    transaction_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_capability(Capability.DEPT_APPROVALS))],
) -> TransactionResponse:
    try:
        txn = approve_transaction(
            db,
            user,
            transaction_id,
            ip_address=_client_ip(request),
        )
    except TransactionError as exc:
        raise _handle_error(exc) from exc
    return _to_response(db, txn, template_names=_template_names(db, [txn]))


@router.post("/{transaction_id}/reject", response_model=TransactionResponse)
def reject_transaction_api(
    transaction_id: uuid.UUID,
    body: RejectTransactionRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_capability(Capability.DEPT_APPROVALS))],
) -> TransactionResponse:
    try:
        txn = reject_transaction(
            db,
            user,
            transaction_id,
            comment=body.comment,
            ip_address=_client_ip(request),
        )
    except TransactionError as exc:
        raise _handle_error(exc) from exc
    return _to_response(db, txn, template_names=_template_names(db, [txn]))


@router.post("/{transaction_id}/preview", response_model=TemplatePreviewResponse)
def preview_transaction_api(
    transaction_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> TemplatePreviewResponse:
    try:
        result = preview_transaction(db, user, transaction_id)
    except TransactionError as exc:
        raise _handle_error(exc) from exc
    return TemplatePreviewResponse(**result)


@router.post("/{transaction_id}/download")
def download_transaction_api(
    transaction_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
    format: Annotated[str, Query(alias="format", description="csv or pdf")] = "csv",
) -> Response:
    try:
        file_bytes, media_type, extension = download_transaction_export(
            db,
            user,
            transaction_id,
            export_format=format,
            ip_address=_client_ip(request),
        )
    except TransactionError as exc:
        raise _handle_error(exc) from exc

    from app.models.export_transaction import ExportTransaction
    from app.models.export_template import ExportTemplate

    txn = db.get(ExportTransaction, transaction_id)
    template_name = "export"
    if txn is not None:
        template = db.get(ExportTemplate, txn.template_id)
        if template is not None:
            template_name = template.name.replace(" ", "_")

    filename = f"{template_name}_{transaction_id.hex[:8]}.{extension}"
    return Response(
        content=file_bytes,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
