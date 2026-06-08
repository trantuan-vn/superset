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
"""Short-lived JWT for Superset Launch Bridge."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import jwt

from app.config import get_settings
from app.models.tenant import Tenant
from app.models.user import User
from app.provisioning.superset_client import SupersetClient
from app.superset.launch import SupersetLaunchTarget, superset_deep_link


def _resolved_superset_username(user: User, tenant: Tenant) -> str:
    client = SupersetClient(get_settings())
    resolved = client.resolve_portal_user(
        tenant.slug,
        portal_username=user.username,
        email=user.email,
    )
    if resolved is not None:
        return resolved.username
    return f"t_{tenant.slug}__{user.username}"


def _launch_secret() -> str:
    settings = get_settings()
    secret = settings.superset_launch_jwt_secret or settings.mcp_jwt_secret
    if not secret:
        raise ValueError("Superset launch JWT secret is not configured")
    return secret


def mint_launch_jwt(
    *,
    user: User,
    tenant: Tenant,
    target: SupersetLaunchTarget,
    resource_id: int,
) -> str:
    """Mint a one-time launch JWT consumed by Superset Launch Bridge."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=settings.superset_launch_jwt_ttl_seconds)
    ss_user = _resolved_superset_username(user, tenant)

    payload = {
        "iss": settings.mcp_jwt_issuer,
        "sub": ss_user,
        "aud": "superset-launch",
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "email": user.email,
        "username": ss_user,
        "tenant_id": str(tenant.id),
        "target": target.value,
        "resource_id": resource_id,
    }
    return jwt.encode(
        payload,
        _launch_secret(),
        algorithm=settings.mcp_jwt_algorithm,
    )


def build_launch_redirect_url(
    *,
    user: User,
    tenant: Tenant,
    target: SupersetLaunchTarget,
    resource_id: int,
) -> str:
    """
    Build the Superset URL opened in a new browser tab.

    The Launch Bridge handler on Superset validates ``portal_launch`` JWT,
    establishes a session for the mapped Superset user, then redirects to
    ``next``.
    """
    settings = get_settings()
    base = settings.superset_public_url.rstrip("/")
    path = superset_deep_link(target, resource_id)

    launch_jwt = mint_launch_jwt(
        user=user,
        tenant=tenant,
        target=target,
        resource_id=resource_id,
    )
    return (
        f"{base}/login/?next={quote(path, safe='')}"
        f"&portal_launch={quote(launch_jwt, safe='')}"
    )
