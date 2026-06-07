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
"""Redis-backed session store."""

import json
import secrets
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import redis

from app.config import get_settings

SESSION_COOKIE_NAME = "portal_session"
SESSION_PREFIX = "portal:session:"
LOGIN_ATTEMPTS_PREFIX = "portal:login_attempts:"


@dataclass
class SessionData:
    """Payload stored in Redis for an authenticated session."""

    session_id: str
    user_id: str
    tenant_id: str
    created_at: str
    expires_at: str
    pki_required: bool = False
    pki_verified: bool = False
    cert_serial: str | None = None


@lru_cache
def get_redis_client() -> redis.Redis:
    settings = get_settings()
    return redis.Redis.from_url(settings.redis_url, decode_responses=True)


def _session_key(session_id: str) -> str:
    return f"{SESSION_PREFIX}{session_id}"


def create_session(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    *,
    pki_required: bool = False,
    pki_verified: bool = False,
    cert_serial: str | None = None,
    ttl_seconds: int | None = None,
) -> tuple[str, int]:
    """Create a session and return (session_id, ttl_seconds)."""
    settings = get_settings()
    if ttl_seconds is None:
        ttl_seconds = settings.session_ttl_hours * 3600
    session_id = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    payload = SessionData(
        session_id=session_id,
        user_id=str(user_id),
        tenant_id=str(tenant_id),
        created_at=now.isoformat(),
        expires_at=expires_at.isoformat(),
        pki_required=pki_required,
        pki_verified=pki_verified if pki_required else True,
        cert_serial=cert_serial,
    )
    client = get_redis_client()
    client.setex(_session_key(session_id), ttl_seconds, json.dumps(asdict(payload)))
    return session_id, ttl_seconds


def update_session(session_id: str, **updates: Any) -> SessionData | None:
    """Merge updates into an existing session and refresh TTL."""
    session = get_session(session_id)
    if session is None:
        return None
    data = asdict(session)
    data.update(updates)
    updated = SessionData(**data)
    settings = get_settings()
    ttl_seconds = settings.session_ttl_hours * 3600
    get_redis_client().setex(
        _session_key(session_id), ttl_seconds, json.dumps(asdict(updated))
    )
    return updated


def get_session(session_id: str) -> SessionData | None:
    """Load session data; returns None when missing or expired."""
    raw = get_redis_client().get(_session_key(session_id))
    if not raw:
        return None
    data: dict[str, Any] = json.loads(raw)
    return SessionData(
        session_id=data["session_id"],
        user_id=data["user_id"],
        tenant_id=data["tenant_id"],
        created_at=data["created_at"],
        expires_at=data["expires_at"],
        pki_required=bool(data.get("pki_required", False)),
        pki_verified=bool(data.get("pki_verified", not data.get("pki_required", False))),
        cert_serial=data.get("cert_serial"),
    )


def delete_session(session_id: str) -> None:
    get_redis_client().delete(_session_key(session_id))


def get_login_attempts(tenant_slug: str, username: str) -> int:
    key = f"{LOGIN_ATTEMPTS_PREFIX}{tenant_slug}:{username.lower()}"
    value = get_redis_client().get(key)
    return int(value) if value else 0


def increment_login_attempts(tenant_slug: str, username: str) -> int:
    settings = get_settings()
    key = f"{LOGIN_ATTEMPTS_PREFIX}{tenant_slug}:{username.lower()}"
    client = get_redis_client()
    attempts = int(client.incr(key))
    if attempts == 1:
        client.expire(key, settings.login_lockout_minutes * 60)
    return attempts


def clear_login_attempts(tenant_slug: str, username: str) -> None:
    key = f"{LOGIN_ATTEMPTS_PREFIX}{tenant_slug}:{username.lower()}"
    get_redis_client().delete(key)
