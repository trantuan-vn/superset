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
"""Short-lived JWT for Superset MCP service — Phase 7."""

from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings
from app.models.tenant import Tenant
from app.models.user import User
from app.provisioning.blueprint import superset_username


def mint_mcp_jwt(*, user: User, tenant: Tenant) -> tuple[str, int]:
    """
    Mint a bearer token accepted by Superset MCP (HS256 by default).

    Returns (token, expires_in_seconds).
    """
    settings = get_settings()
    if not settings.mcp_jwt_secret:
        raise ValueError("MCP JWT secret is not configured")

    ttl_seconds = settings.mcp_jwt_ttl_minutes * 60
    now = datetime.now(timezone.utc)
    expires = now + timedelta(seconds=ttl_seconds)
    superset_user = superset_username(tenant.slug, user.username)

    payload = {
        "iss": settings.mcp_jwt_issuer,
        "sub": superset_user,
        "aud": settings.mcp_jwt_audience,
        "iat": int(now.timestamp()),
        "exp": int(expires.timestamp()),
        "email": user.email,
        "username": superset_user,
        "tenant_id": str(tenant.id),
        "scopes": ["superset:read", "superset:sql_lab:write"],
    }

    token = jwt.encode(
        payload,
        settings.mcp_jwt_secret,
        algorithm=settings.mcp_jwt_algorithm,
    )
    return token, ttl_seconds
