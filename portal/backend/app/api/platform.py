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
"""Platform operator API — onboard tenants and tenant administrators."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.api.schemas import (
    CreateTenantAdminRequest,
    CreateTenantRequest,
    CreateTenantResponse,
    PlatformTenantResponse,
    TenantAdminResponse,
)
from app.auth.dependencies import require_platform_admin
from app.auth.service import AuthError
from app.db import get_db
from app.models.user import User
from app.platform.service import add_tenant_admin, create_tenant_with_admin, list_tenants

router = APIRouter(prefix="/platform", tags=["platform"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("/tenants", response_model=list[PlatformTenantResponse])
def get_platform_tenants(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_platform_admin)],
) -> list[PlatformTenantResponse]:
    rows = list_tenants(db)
    return [
        PlatformTenantResponse(
            id=str(row.id),
            slug=row.slug,
            name=row.name,
            status=row.status,
            admin_count=row.admin_count,
            pki_enabled=row.pki_enabled,
        )
        for row in rows
    ]


@router.post("/tenants", response_model=CreateTenantResponse, status_code=201)
def post_platform_tenant(
    body: CreateTenantRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[User, Depends(require_platform_admin)],
) -> CreateTenantResponse:
    try:
        result = create_tenant_with_admin(
            db,
            slug=body.slug,
            name=body.name,
            admin_email=body.admin_email,
            admin_password=body.admin_password,
            admin_display_name=body.admin_display_name,
            actor_id=actor.id,
            ip_address=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return CreateTenantResponse(
        tenant=PlatformTenantResponse(
            id=str(result.tenant.id),
            slug=result.tenant.slug,
            name=result.tenant.name,
            status=result.tenant.status.value,
            admin_count=1,
            pki_enabled=False,
        ),
        admin=TenantAdminResponse(
            id=str(result.admin_user.id),
            email=result.admin_user.email,
            display_name=result.admin_user.display_name,
        ),
    )


@router.post(
    "/tenants/{tenant_id}/admins",
    response_model=TenantAdminResponse,
    status_code=201,
)
def post_tenant_admin(
    tenant_id: uuid.UUID,
    body: CreateTenantAdminRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    actor: Annotated[User, Depends(require_platform_admin)],
) -> TenantAdminResponse:
    try:
        admin = add_tenant_admin(
            db,
            tenant_id=tenant_id,
            admin_email=body.admin_email,
            admin_password=body.admin_password,
            admin_display_name=body.admin_display_name,
            actor_id=actor.id,
            ip_address=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return TenantAdminResponse(
        id=str(admin.id),
        email=admin.email,
        display_name=admin.display_name,
    )
