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
"""Authentication API — Phase 1 local login."""

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.api.schemas import (
    LoginRequest,
    MeResponse,
    MessageResponse,
    TenantResponse,
    UserDeptRoleResponse,
    UserResponse,
    branding_from_json,
)
from app.auth.dependencies import get_current_user, get_session_data, get_session_id
from app.auth.pki_service import reconcile_session_pki_with_tenant, session_needs_pki
from app.auth.session import SessionData
from app.auth.service import AuthError, get_me, login, logout
from app.auth.session import SESSION_COOKIE_NAME
from app.config import get_settings
from app.db import get_db
from app.departments.service import load_user_dept_roles
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _set_session_cookie(response: Response, session_id: str, max_age: int) -> None:
    settings = get_settings()
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=session_id,
        max_age=max_age,
        httponly=True,
        samesite=settings.session_cookie_samesite,
        secure=settings.session_cookie_secure,
        path="/",
    )


def _clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


def _user_response(user: User, db: Session) -> UserResponse:
    dept_roles = load_user_dept_roles(db, user.id)
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        system_role=user.system_role.value,
        departments=[UserDeptRoleResponse(**role) for role in dept_roles],
    )


@router.post("/login", response_model=MeResponse)
def auth_login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
) -> MeResponse:
    try:
        result = login(
            db,
            tenant_slug=body.tenant_slug.strip(),
            username=body.username.strip(),
            password=body.password,
            ip_address=_client_ip(request),
        )
    except AuthError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    _set_session_cookie(response, result.session_id, result.ttl_seconds)
    return MeResponse(
        user=_user_response(result.user, db),
        tenant=TenantResponse(
            id=str(result.tenant.id),
            slug=result.tenant.slug,
            name=result.tenant.name,
            branding=branding_from_json(result.settings.branding),
        ),
        pki_pending=result.pki_pending,
    )


@router.post("/logout", response_model=MessageResponse)
def auth_logout(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    session_id: Annotated[str, Depends(get_session_id)],
    user: Annotated[User, Depends(get_current_user)],
) -> MessageResponse:
    logout(db, session_id=session_id, user=user, ip_address=_client_ip(request))
    _clear_session_cookie(response)
    return MessageResponse(message="Logged out")


@router.get("/me", response_model=MeResponse)
def auth_me(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[SessionData, Depends(get_session_data)],
    session_id: Annotated[str, Depends(get_session_id)],
) -> MeResponse:
    try:
        result = get_me(db, user.id)
    except AuthError as exc:
        from fastapi import HTTPException

        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    session = reconcile_session_pki_with_tenant(
        session, session_id, result.settings
    )

    return MeResponse(
        user=_user_response(result.user, db),
        tenant=TenantResponse(
            id=str(result.tenant.id),
            slug=result.tenant.slug,
            name=result.tenant.name,
            branding=branding_from_json(result.settings.branding),
        ),
        pki_pending=session_needs_pki(session),
        cert_serial=session.cert_serial,
    )
