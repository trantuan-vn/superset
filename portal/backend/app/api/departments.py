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
"""Department administration API — Phase 4."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.schemas import (
    CreateDepartmentRequest,
    DepartmentResponse,
    UpdateDepartmentRequest,
)
from app.auth.dependencies import require_tenant_admin_or_cntt_lanhdao
from app.db import get_db
from app.departments.service import (
    DeptError,
    DepartmentListFilters,
    create_department,
    department_to_dict,
    get_department,
    list_departments,
    update_department,
)
from app.models.department import DepartmentStatus
from app.models.user import User

router = APIRouter(prefix="/departments", tags=["departments"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


@router.get("", response_model=list[DepartmentResponse])
def list_departments_api(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
    search: Annotated[str | None, Query()] = None,
    status: Annotated[str | None, Query()] = None,
) -> list[DepartmentResponse]:
    status_filter: DepartmentStatus | None = None
    if status is not None:
        try:
            status_filter = DepartmentStatus(status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid status filter") from exc

    departments = list_departments(
        db,
        user.tenant_id,
        filters=DepartmentListFilters(search=search, status=status_filter),
    )
    return [DepartmentResponse(**department_to_dict(d)) for d in departments]


@router.post("", response_model=DepartmentResponse, status_code=201)
def create_department_api(
    body: CreateDepartmentRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
) -> DepartmentResponse:
    try:
        dept = create_department(
            db,
            tenant_id=user.tenant_id,
            code=body.code,
            name=body.name,
            actor=user,
            ip_address=_client_ip(request),
        )
    except DeptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return DepartmentResponse(**department_to_dict(dept))


@router.get("/{department_id}", response_model=DepartmentResponse)
def get_department_api(
    department_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
) -> DepartmentResponse:
    try:
        dept = get_department(db, user.tenant_id, department_id)
    except DeptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return DepartmentResponse(**department_to_dict(dept))


@router.patch("/{department_id}", response_model=DepartmentResponse)
def update_department_api(
    department_id: uuid.UUID,
    body: UpdateDepartmentRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
) -> DepartmentResponse:
    status_value: DepartmentStatus | None = None
    if body.status is not None:
        try:
            status_value = DepartmentStatus(body.status)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="Invalid status") from exc

    try:
        dept = update_department(
            db,
            tenant_id=user.tenant_id,
            department_id=department_id,
            name=body.name,
            status=status_value,
            actor=user,
            ip_address=_client_ip(request),
        )
    except DeptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return DepartmentResponse(**department_to_dict(dept))
