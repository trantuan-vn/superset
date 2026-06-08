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
"""Validate Portal launch JWT and establish a Superset browser session."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

import jwt
from flask import current_app, redirect
from flask_login import login_user
from werkzeug.wrappers import Response as WerkzeugResponse

if TYPE_CHECKING:
    from werkzeug.wrappers import Request

logger = logging.getLogger(__name__)


def _launch_config(name: str, default: Any = None) -> Any:
    return current_app.config.get(name, default)


def _launch_enabled() -> bool:
    return bool(_launch_config("PORTAL_LAUNCH_ENABLED", False))


def _launch_secret() -> str | None:
    secret = _launch_config("PORTAL_LAUNCH_JWT_SECRET") or _launch_config(
        "MCP_JWT_SECRET"
    )
    if secret:
        return str(secret)
    return None


def safe_next_path(next_url: str | None, *, fallback: str) -> str:
    """Allow only same-origin relative paths for post-login redirect."""
    if not next_url:
        return fallback
    if next_url.startswith("/") and not next_url.startswith("//"):
        return next_url
    return fallback


def decode_portal_launch_token(token: str) -> dict[str, Any] | None:
    """Verify HS256 launch JWT from Portal; return claims or None."""
    secret = _launch_secret()
    if not secret:
        logger.warning("Portal launch JWT secret is not configured")
        return None

    issuer = _launch_config("PORTAL_LAUNCH_JWT_ISSUER", "portal")
    audience = _launch_config("PORTAL_LAUNCH_JWT_AUDIENCE", "superset-launch")
    algorithm = _launch_config("PORTAL_LAUNCH_JWT_ALGORITHM", "HS256")

    try:
        return jwt.decode(
            token,
            secret,
            algorithms=[algorithm],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "sub"]},
        )
    except jwt.PyJWTError as exc:
        logger.warning("Portal launch JWT rejected: %s", type(exc).__name__)
        return None


def try_portal_launch_login(
    request: Request,
    *,
    fallback_url: str,
) -> WerkzeugResponse | None:
    """
    If ``portal_launch`` query param is present, validate JWT and log in.

    Returns a redirect response on success, or None to fall through to the
    normal login page.
    """
    if not _launch_enabled():
        return None

    token = request.args.get("portal_launch")
    if not token:
        return None

    claims = decode_portal_launch_token(token)
    if claims is None:
        return None

    username = str(claims.get("sub") or claims.get("username") or "").strip()
    if not username:
        logger.warning("Portal launch JWT missing subject")
        return None

    from superset import security_manager

    user = security_manager.find_user(username=username)
    if user is None or not user.is_active:
        logger.warning("Portal launch user not found or inactive: %s", username)
        return None

    login_user(user, remember=False)
    security_manager.on_user_login(user)

    next_path = safe_next_path(request.args.get("next"), fallback=fallback_url)
    logger.info("Portal launch login succeeded for %s -> %s", username, next_path)
    return redirect(next_path)
