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
"""Tenant administration API — Phase 2 settings."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.schemas import (
    PkiCaUploadRequest,
    TenantSettingsPatch,
    TenantSettingsResponse,
)
from app.auth.dependencies import require_tenant_admin
from app.auth.service import AuthError
from app.db import get_db
from app.models.user import User
from app.tenants.service import (
    get_tenant_settings,
    remove_tenant_ca_certificate,
    settings_to_response,
    update_tenant_settings,
    upload_tenant_ca_certificate,
)

router = APIRouter(prefix="/tenants", tags=["tenants"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("/{tenant_id}/settings", response_model=TenantSettingsResponse)
def get_settings(
    tenant_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin)],
) -> TenantSettingsResponse:
    if user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied for this tenant")
    try:
        settings = get_tenant_settings(db, tenant_id)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return TenantSettingsResponse(**settings_to_response(settings, db=db))


@router.patch("/{tenant_id}/settings", response_model=TenantSettingsResponse)
def patch_settings(
    tenant_id: uuid.UUID,
    body: TenantSettingsPatch,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin)],
) -> TenantSettingsResponse:
    if user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied for this tenant")

    patch = body.model_dump(exclude_unset=True)
    try:
        settings = update_tenant_settings(
            db,
            tenant_id=tenant_id,
            actor=user,
            patch=patch,
            ip_address=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return TenantSettingsResponse(**settings_to_response(settings, db=db))


@router.post(
    "/{tenant_id}/settings/pki/ca-certificate",
    response_model=TenantSettingsResponse,
)
def upload_ca_certificate(
    tenant_id: uuid.UUID,
    body: PkiCaUploadRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin)],
) -> TenantSettingsResponse:
    if user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied for this tenant")
    try:
        settings = upload_tenant_ca_certificate(
            db,
            tenant_id=tenant_id,
            actor=user,
            certificate_pem=body.certificate,
            ip_address=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return TenantSettingsResponse(**settings_to_response(settings, db=db))


@router.delete(
    "/{tenant_id}/settings/pki/ca-certificate",
    response_model=TenantSettingsResponse,
)
def delete_ca_certificate(
    tenant_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin)],
) -> TenantSettingsResponse:
    if user.tenant_id != tenant_id:
        raise HTTPException(status_code=403, detail="Access denied for this tenant")
    try:
        settings = remove_tenant_ca_certificate(
            db,
            tenant_id=tenant_id,
            actor=user,
            ip_address=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return TenantSettingsResponse(**settings_to_response(settings, db=db))
