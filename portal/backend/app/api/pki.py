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
"""PKI authentication endpoints — Phase 3."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.api.schemas import (
    MeResponse,
    PkiChallengeResponse,
    PkiVerifyRequest,
    PkiVerifyResponse,
    TenantResponse,
    UserResponse,
    branding_from_json,
)
from app.auth.dependencies import get_session_data
from app.auth.pki_service import create_pki_challenge, session_needs_pki, verify_pki_login
from app.auth.service import AuthError
from app.auth.session import SessionData
from app.db import get_db
from app.models.tenant import Tenant
from app.models.user import User, UserStatus

router = APIRouter(prefix="/auth/pki", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _load_user_for_session(db: Session, session: SessionData) -> User:
    import uuid

    user = db.scalar(
        select(User)
        .options(joinedload(User.tenant).joinedload(Tenant.settings))
        .where(User.id == uuid.UUID(session.user_id))
    )
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    if str(user.tenant_id) != session.tenant_id:
        raise HTTPException(status_code=403, detail="Tenant mismatch")
    return user


def _user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        display_name=user.display_name,
        system_role=user.system_role.value,
    )


@router.post("/challenge", response_model=PkiChallengeResponse)
def pki_challenge(
    session: Annotated[SessionData, Depends(get_session_data)],
) -> PkiChallengeResponse:
    if not session_needs_pki(session):
        raise HTTPException(
            status_code=400,
            detail="PKI challenge not required for this session",
        )
    try:
        result = create_pki_challenge(session)
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return PkiChallengeResponse(
        nonce=result.nonce,
        expires_in_seconds=result.expires_in_seconds,
    )


@router.post("/verify", response_model=PkiVerifyResponse)
def pki_verify(
    body: PkiVerifyRequest,
    request: Request,
    session: Annotated[SessionData, Depends(get_session_data)],
    db: Annotated[Session, Depends(get_db)],
) -> PkiVerifyResponse:
    if not session_needs_pki(session):
        raise HTTPException(
            status_code=400,
            detail="PKI verification not required for this session",
        )

    user = _load_user_for_session(db, session)
    settings = user.tenant.settings
    if settings is None:
        raise HTTPException(status_code=500, detail="Tenant settings not found")

    try:
        result = verify_pki_login(
            db,
            session=session,
            user=user,
            settings=settings,
            certificate_pem=body.certificate.strip(),
            signature=body.signature.strip(),
            ip_address=_client_ip(request),
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    return PkiVerifyResponse(
        cert_serial=result.cert_serial,
        subject_dn=result.subject_dn,
    )


@router.get("/status", response_model=MeResponse)
def pki_status(
    session: Annotated[SessionData, Depends(get_session_data)],
    db: Annotated[Session, Depends(get_db)],
) -> MeResponse:
    """Session PKI state for the wizard UI."""
    user = _load_user_for_session(db, session)
    tenant = user.tenant
    settings = tenant.settings
    return MeResponse(
        user=_user_response(user),
        tenant=TenantResponse(
            id=str(tenant.id),
            slug=tenant.slug,
            name=tenant.name,
            ai_enabled=settings.ai_enabled if settings else False,
            branding=branding_from_json(settings.branding if settings else None),
        ),
        pki_pending=session_needs_pki(session),
        cert_serial=session.cert_serial,
    )
