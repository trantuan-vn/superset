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
"""SSO authentication endpoints — Phase 2."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.api.schemas import LoginOptionsResponse, branding_from_json
from app.auth.service import AuthError
from app.auth.session import SESSION_COOKIE_NAME
from app.auth.sso_service import complete_oidc_callback, get_login_options, start_oidc_login
from app.config import get_settings
from app.db import get_db

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


@router.get("/login-options", response_model=LoginOptionsResponse)
def auth_login_options(
    tenant_slug: Annotated[str, Query(min_length=1, max_length=128)],
    db: Annotated[Session, Depends(get_db)],
) -> LoginOptionsResponse:
    try:
        options = get_login_options(db, tenant_slug=tenant_slug.strip())
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    branding = branding_from_json(options.get("branding"))
    return LoginOptionsResponse(
        tenant_slug=options["tenant_slug"],
        tenant_name=options["tenant_name"],
        sso_enabled=options["sso_enabled"],
        auth_mode=options["auth_mode"],
        sso_primary=options["sso_primary"],
        show_local_login=options["show_local_login"],
        branding=branding,
    )


@router.get("/sso/login")
def auth_sso_login(
    tenant_slug: Annotated[str, Query(min_length=1, max_length=128)],
    db: Annotated[Session, Depends(get_db)],
) -> RedirectResponse:
    try:
        result = start_oidc_login(db, tenant_slug=tenant_slug.strip())
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return RedirectResponse(url=result.redirect_url, status_code=302)


@router.get("/sso/callback")
def auth_sso_callback(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    settings = get_settings()
    frontend = settings.frontend_base_url.rstrip("/")

    if error:
        return RedirectResponse(
            url=f"{frontend}/login?sso_error={error}",
            status_code=302,
        )
    if not code or not state:
        return RedirectResponse(
            url=f"{frontend}/login?sso_error=missing_code",
            status_code=302,
        )

    try:
        result = complete_oidc_callback(
            db, code=code, state=state, ip_address=_client_ip(request)
        )
    except AuthError as exc:
        return RedirectResponse(
            url=f"{frontend}/login?sso_error={exc.message}",
            status_code=302,
        )

    response = RedirectResponse(url=f"{frontend}/dashboard", status_code=302)
    _set_session_cookie(response, result.session_id, result.ttl_seconds)
    return response
