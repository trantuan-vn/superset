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
"""Export template workflow API — Phase 8."""

import hashlib
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import (
    CreateTemplateRequest,
    PkiStepUpChallengeResponse,
    TemplateApproveRequest,
    TemplateLaunchUrlResponse,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateRejectRequest,
    TemplateResponse,
    UpdateTemplateRequest,
)
from app.auth.dependencies import get_current_user_with_dept_roles, get_session_data
from app.auth.pki_service import create_pki_stepup_challenge, verify_pki_step_up
from app.auth.service import AuthError
from app.auth.session import SessionData
from app.db import get_db
from app.models.export_template import TemplateShareMode, TemplateStatus
from app.models.tenant import Tenant, TenantSettings
from app.models.user import User
from app.superset.launch import SupersetLaunchTarget
from app.templates.access import shared_department_rows
from app.templates.service import (
    TemplateError,
    TemplateListFilters,
    approve_template,
    create_template,
    delete_template,
    get_template,
    get_template_launch_url,
    list_templates,
    preview_template_sql,
    push_template_dataset,
    reject_template,
    submit_template,
    sync_template_dashboard,
    template_to_dict,
    update_template,
)

router = APIRouter(prefix="/templates", tags=["templates"])

STEPUP_ACTION_TEMPLATE_APPROVE = "template_approve"


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _load_settings(db: Session, tenant_id: uuid.UUID) -> TenantSettings:
    settings = db.get(TenantSettings, tenant_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="Tenant settings not found")
    return settings


def _load_tenant(db: Session, tenant_id: uuid.UUID) -> Tenant:
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


def _creator_names(db: Session, templates: list) -> dict[uuid.UUID, str]:
    creator_ids = {template.created_by for template in templates}
    if not creator_ids:
        return {}
    users = db.scalars(select(User).where(User.id.in_(creator_ids))).all()
    return {user.id: user.display_name for user in users}


def _to_response(
    db: Session,
    template,
    *,
    creator_names: dict[uuid.UUID, str] | None = None,
) -> TemplateResponse:
    names = creator_names or {}
    return TemplateResponse(
        **template_to_dict(
            template,
            creator_name=names.get(template.created_by),
            shared_departments=shared_department_rows(db, template),
        )
    )


def _handle_template_error(exc: TemplateError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("", response_model=list[TemplateResponse])
def list_templates_api(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
    status: Annotated[str | None, Query()] = None,
    pending: Annotated[bool, Query()] = False,
) -> list[TemplateResponse]:
    status_filter: TemplateStatus | None = None
    if status is not None:
        try:
            status_filter = TemplateStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid status filter") from exc

    try:
        templates = list_templates(
            db,
            user,
            filters=TemplateListFilters(status=status_filter, pending_only=pending),
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc

    names = _creator_names(db, templates)
    return [_to_response(db, template, creator_names=names) for template in templates]


@router.post("", response_model=TemplateResponse, status_code=201)
def create_template_api(
    body: CreateTemplateRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> TemplateResponse:
    try:
        template = create_template(
            db,
            user,
            name=body.name,
            description=body.description,
            sql_snapshot=body.sql_snapshot,
            ip_address=_client_ip(request),
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc
    return _to_response(db, template, creator_names={user.id: user.display_name})


@router.post("/pki/step-up/challenge", response_model=PkiStepUpChallengeResponse)
def template_stepup_challenge_api(
    session: Annotated[SessionData, Depends(get_session_data)],
    action: Annotated[str, Query()] = STEPUP_ACTION_TEMPLATE_APPROVE,
) -> PkiStepUpChallengeResponse:
    result = create_pki_stepup_challenge(session, action)
    return PkiStepUpChallengeResponse(
        nonce=result.nonce,
        expires_in_seconds=result.expires_in_seconds,
        action=action,
    )


@router.get("/{template_id}", response_model=TemplateResponse)
def get_template_api(
    template_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> TemplateResponse:
    try:
        template = get_template(db, user, template_id)
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc
    names = _creator_names(db, [template])
    return _to_response(db, template, creator_names=names)


@router.delete("/{template_id}", status_code=204)
def delete_template_api(
    template_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> None:
    try:
        delete_template(
            db,
            user,
            template_id,
            ip_address=_client_ip(request),
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc


@router.patch("/{template_id}", response_model=TemplateResponse)
def update_template_api(
    template_id: uuid.UUID,
    body: UpdateTemplateRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> TemplateResponse:
    try:
        template = update_template(
            db,
            user,
            template_id,
            name=body.name,
            description=body.description,
            sql_snapshot=body.sql_snapshot,
            ip_address=_client_ip(request),
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc
    return _to_response(db, template, creator_names={user.id: user.display_name})


@router.post("/{template_id}/submit", response_model=TemplateResponse)
def submit_template_api(
    template_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> TemplateResponse:
    tenant = _load_tenant(db, user.tenant_id)
    try:
        template = submit_template(
            db,
            user,
            template_id,
            tenant=tenant,
            ip_address=_client_ip(request),
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc
    return _to_response(db, template, creator_names={user.id: user.display_name})


@router.post("/{template_id}/push-dataset", response_model=TemplateResponse)
def push_template_dataset_api(
    template_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> TemplateResponse:
    try:
        template = push_template_dataset(
            db,
            user,
            template_id,
            ip_address=_client_ip(request),
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc
    return _to_response(db, template, creator_names={user.id: user.display_name})


@router.post("/{template_id}/sync-dashboard", response_model=TemplateResponse)
def sync_template_dashboard_api(
    template_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> TemplateResponse:
    tenant = _load_tenant(db, user.tenant_id)
    try:
        template = sync_template_dashboard(
            db,
            user,
            template_id,
            tenant=tenant,
            ip_address=_client_ip(request),
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc
    return _to_response(db, template, creator_names={user.id: user.display_name})


@router.get("/{template_id}/launch-url", response_model=TemplateLaunchUrlResponse)
def template_launch_url_api(
    template_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
    target: Annotated[str, Query(description="dataset|dashboard_design|dashboard_review|dashboard_view")] = "dataset",
) -> TemplateLaunchUrlResponse:
    tenant = _load_tenant(db, user.tenant_id)
    try:
        launch_target = SupersetLaunchTarget(target)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid launch target") from exc
    try:
        url = get_template_launch_url(
            db,
            user,
            template_id,
            tenant=tenant,
            target=launch_target,
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc
    return TemplateLaunchUrlResponse(url=url, target=target)


@router.post("/{template_id}/reject", response_model=TemplateResponse)
def reject_template_api(
    template_id: uuid.UUID,
    body: TemplateRejectRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> TemplateResponse:
    try:
        template = reject_template(
            db,
            user,
            template_id,
            comment=body.comment,
            ip_address=_client_ip(request),
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc
    names = _creator_names(db, [template])
    return _to_response(db, template, creator_names=names)


@router.post("/{template_id}/approve", response_model=TemplateResponse)
def approve_template_api(
    template_id: uuid.UUID,
    body: TemplateApproveRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
    session: Annotated[SessionData, Depends(get_session_data)],
) -> TemplateResponse:
    settings = _load_settings(db, user.tenant_id)
    tenant = _load_tenant(db, user.tenant_id)
    pki_config = settings.pki_config or {}
    signature_hash: str | None = None
    cert_serial: str | None = None

    try:
        share_mode = TemplateShareMode(body.share_mode)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid share_mode") from exc

    department_ids: list[uuid.UUID] = []
    for raw_id in body.department_ids:
        try:
            department_ids.append(uuid.UUID(raw_id))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid department id") from exc

    if settings.digital_signature_enabled and pki_config.get("require_cert_at_approval"):
        if not body.certificate or not body.signature:
            raise HTTPException(
                status_code=403,
                detail="Digital signature required for template approval",
            )
        try:
            verified = verify_pki_step_up(
                db,
                session=session,
                user=user,
                settings=settings,
                action=STEPUP_ACTION_TEMPLATE_APPROVE,
                certificate_pem=body.certificate,
                signature=body.signature,
                ip_address=_client_ip(request),
            )
        except AuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        signature_hash = hashlib.sha256(body.signature.encode()).hexdigest()
        cert_serial = verified.cert_serial

    try:
        template = approve_template(
            db,
            user,
            template_id,
            tenant=tenant,
            settings=settings,
            share_mode=share_mode,
            department_ids=department_ids or None,
            ip_address=_client_ip(request),
            signature_payload_hash=signature_hash,
            signer_cert_serial=cert_serial,
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc

    names = _creator_names(db, [template])
    return _to_response(db, template, creator_names=names)


@router.post("/{template_id}/preview", response_model=TemplatePreviewResponse)
def preview_template_api(
    template_id: uuid.UUID,
    body: TemplatePreviewRequest,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> TemplatePreviewResponse:
    try:
        result = preview_template_sql(
            db,
            user,
            template_id,
            sql_override=body.sql,
        )
    except TemplateError as exc:
        raise _handle_template_error(exc) from exc
    return TemplatePreviewResponse(**result)
