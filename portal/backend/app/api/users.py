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
"""User administration API — Phase 4."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.api.schemas import (
    AssignDeptRoleRequest,
    CreateUserRequest,
    MessageResponse,
    SetUserPasswordRequest,
    UpdateUserRequest,
    UserAdminResponse,
)
from app.auth.dependencies import require_tenant_admin_or_cntt_lanhdao
from app.db import get_db
from app.departments.service import (
    DeptError,
    assign_dept_role,
    create_user,
    get_user_in_tenant,
    list_users,
    remove_dept_role,
    set_user_password,
    update_user,
    user_to_dict,
)
from app.models.department import DeptRole
from app.models.user import SystemRole, User, UserStatus

router = APIRouter(prefix="/users", tags=["users"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _parse_system_role(value: str) -> SystemRole:
    try:
        return SystemRole(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid system_role") from exc


def _parse_user_status(value: str) -> UserStatus:
    try:
        return UserStatus(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid status") from exc


def _parse_dept_role(value: str) -> DeptRole:
    try:
        return DeptRole(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid dept role") from exc


@router.get("", response_model=list[UserAdminResponse])
def list_users_api(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
    search: Annotated[str | None, Query()] = None,
    system_role: Annotated[str | None, Query()] = None,
) -> list[UserAdminResponse]:
    role_filter: SystemRole | None = None
    if system_role is not None:
        role_filter = _parse_system_role(system_role)

    users = list_users(
        db,
        user.tenant_id,
        search=search,
        system_role=role_filter,
    )
    return [UserAdminResponse(**user_to_dict(u)) for u in users]


@router.post("", response_model=UserAdminResponse, status_code=201)
def create_user_api(
    body: CreateUserRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
) -> UserAdminResponse:
    try:
        created = create_user(
            db,
            tenant_id=user.tenant_id,
            username=body.username,
            email=body.email,
            display_name=body.display_name,
            password=body.password,
            system_role=_parse_system_role(body.system_role),
            actor=user,
            ip_address=_client_ip(request),
        )
    except DeptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return UserAdminResponse(**user_to_dict(created))


@router.get("/{user_id}", response_model=UserAdminResponse)
def get_user_api(
    user_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
) -> UserAdminResponse:
    try:
        target = get_user_in_tenant(db, user.tenant_id, user_id)
    except DeptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return UserAdminResponse(**user_to_dict(target))


@router.patch("/{user_id}", response_model=UserAdminResponse)
def update_user_api(
    user_id: uuid.UUID,
    body: UpdateUserRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
) -> UserAdminResponse:
    status_value: UserStatus | None = None
    if body.status is not None:
        status_value = _parse_user_status(body.status)

    try:
        updated = update_user(
            db,
            tenant_id=user.tenant_id,
            user_id=user_id,
            display_name=body.display_name,
            email=body.email,
            status=status_value,
            actor=user,
            ip_address=_client_ip(request),
        )
    except DeptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return UserAdminResponse(**user_to_dict(updated))


@router.post("/{user_id}/password", response_model=MessageResponse)
def set_user_password_api(
    user_id: uuid.UUID,
    body: SetUserPasswordRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
) -> MessageResponse:
    try:
        set_user_password(
            db,
            tenant_id=user.tenant_id,
            user_id=user_id,
            password=body.password,
            actor=user,
            ip_address=_client_ip(request),
        )
    except DeptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return MessageResponse(message="Password updated and Superset sync queued")


@router.post("/{user_id}/dept-roles", response_model=UserAdminResponse)
def assign_dept_role_api(
    user_id: uuid.UUID,
    body: AssignDeptRoleRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
) -> UserAdminResponse:
    try:
        dept_id = uuid.UUID(body.department_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Invalid department_id") from exc

    try:
        updated = assign_dept_role(
            db,
            tenant_id=user.tenant_id,
            user_id=user_id,
            department_id=dept_id,
            role=_parse_dept_role(body.role),
            actor=user,
            ip_address=_client_ip(request),
        )
    except DeptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return UserAdminResponse(**user_to_dict(updated))


@router.delete("/{user_id}/dept-roles/{department_id}", response_model=MessageResponse)
def remove_dept_role_api(
    user_id: uuid.UUID,
    department_id: uuid.UUID,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin_or_cntt_lanhdao)],
) -> MessageResponse:
    try:
        remove_dept_role(
            db,
            tenant_id=user.tenant_id,
            user_id=user_id,
            department_id=department_id,
            actor=user,
            ip_address=_client_ip(request),
        )
    except DeptError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return MessageResponse(message="Department role removed")
