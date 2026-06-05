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
"""SSO login orchestration — OIDC redirect and LDAP profile linking."""

import json
import secrets
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.auth.adapters.ldap import LdapAuthError, LdapAuthResult, authenticate_ldap
from app.auth.adapters.oidc import (
    OidcAuthError,
    OidcProfile,
    build_authorization_url,
    exchange_code_for_profile,
    oidc_redirect_uri,
)
from app.auth.service import AuthError, LoginResult, _get_tenant_by_slug
from app.auth.serialize import json_safe_attributes
from app.auth.session import create_session, get_redis_client
from app.models.tenant import AuthMode, Tenant, TenantSettings
from app.models.user import SystemRole, User, UserStatus
from app.models.user_auth import AuthProvider, UserAuthIdentity

OAUTH_STATE_PREFIX = "portal:oauth_state:"
OAUTH_STATE_TTL = 600


@dataclass
class SsoLoginStart:
    redirect_url: str


@dataclass
class ExternalProfile:
    external_id: str
    email: str
    display_name: str
    dept_code: str | None
    raw_attributes: dict[str, Any]
    provider: AuthProvider


def _oauth_state_key(state: str) -> str:
    return f"{OAUTH_STATE_PREFIX}{state}"


def _store_oauth_state(tenant_slug: str) -> str:
    state = secrets.token_urlsafe(24)
    payload = json.dumps({"tenant_slug": tenant_slug})
    get_redis_client().setex(_oauth_state_key(state), OAUTH_STATE_TTL, payload)
    return state


def _pop_oauth_state(state: str) -> str | None:
    key = _oauth_state_key(state)
    client = get_redis_client()
    raw = client.get(key)
    if raw:
        client.delete(key)
        data = json.loads(raw)
        return str(data.get("tenant_slug", ""))
    return None


def _get_tenant_settings(db: Session, tenant_id: uuid.UUID) -> TenantSettings:
    settings = db.get(TenantSettings, tenant_id)
    if settings is None:
        raise AuthError("Tenant settings not found", status_code=500)
    return settings


def _ensure_sso_enabled(settings: TenantSettings) -> None:
    if not settings.sso_ldap_enabled:
        raise AuthError("SSO is not enabled for this tenant", status_code=403)


def _role_from_uid(uid: str) -> SystemRole:
    """Map demo LDAP/Keycloak uids to Portal system roles."""
    base = uid.split("@", 1)[0].lower()
    if base.startswith("cntt.ld") or base == "cntt.ld":
        return SystemRole.CNTT_LANHDAO
    if base.startswith("cntt.") or base == "cntt.cv":
        return SystemRole.CNTT_CHUYENVIEN
    if base in ("admin", "admin@demo-corp") or base.startswith("admin"):
        return SystemRole.TENANT_ADMIN
    return SystemRole.DEPT_USER


def _find_user_by_identity(
    db: Session,
    tenant_id: uuid.UUID,
    provider: AuthProvider,
    external_id: str,
) -> User | None:
    stmt = (
        select(User)
        .join(UserAuthIdentity, UserAuthIdentity.user_id == User.id)
        .where(
            User.tenant_id == tenant_id,
            UserAuthIdentity.provider == provider,
            UserAuthIdentity.external_id == external_id,
        )
    )
    return db.scalar(stmt)


def _find_user_by_email(db: Session, tenant_id: uuid.UUID, email: str) -> User | None:
    normalized = email.strip().lower()
    stmt = select(User).where(
        User.tenant_id == tenant_id,
        (User.email == normalized) | (User.username == normalized),
    )
    return db.scalar(stmt)


def _upsert_identity(
    db: Session,
    user: User,
    provider: AuthProvider,
    profile: ExternalProfile,
) -> None:
    identity = db.scalar(
        select(UserAuthIdentity).where(
            UserAuthIdentity.user_id == user.id,
            UserAuthIdentity.provider == provider,
        )
    )
    if identity is None:
        identity = UserAuthIdentity(
            user_id=user.id,
            provider=provider,
            external_id=profile.external_id,
        )
        db.add(identity)
    identity.external_id = profile.external_id
    identity.raw_attributes = {
        **json_safe_attributes(profile.raw_attributes),
        "dept_code": profile.dept_code,
    }


def _provision_sso_user(
    db: Session,
    tenant: Tenant,
    profile: ExternalProfile,
) -> User:
    """Find or create a Portal user from an external directory profile."""
    user = _find_user_by_identity(
        db, tenant.id, profile.provider, profile.external_id
    )
    if user is None:
        user = _find_user_by_email(db, tenant.id, profile.email)

    username = profile.email.strip().lower()
    uid_base = profile.external_id.split("@", 1)[0]

    if user is None:
        user = User(
            tenant_id=tenant.id,
            username=username,
            email=profile.email.strip().lower(),
            display_name=profile.display_name,
            password_hash=None,
            system_role=_role_from_uid(uid_base),
            status=UserStatus.ACTIVE,
        )
        db.add(user)
        db.flush()
    else:
        user.display_name = profile.display_name
        if user.status == UserStatus.INACTIVE:
            raise AuthError("Account is inactive", status_code=403)
        if user.status == UserStatus.LOCKED:
            raise AuthError("Account is locked", status_code=403)

    _upsert_identity(db, user, profile.provider, profile)
    return user


def _complete_sso_login(
    db: Session,
    *,
    tenant: Tenant,
    settings: TenantSettings,
    user: User,
    provider: AuthProvider,
    ip_address: str | None,
) -> LoginResult:
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    session_id, ttl_seconds = create_session(user.id, tenant.id)
    write_audit_log(
        db,
        tenant_id=tenant.id,
        action="AUTH_SSO_LOGIN",
        entity_type="user",
        entity_id=str(user.id),
        actor_id=user.id,
        payload={"method": provider.value},
        ip_address=ip_address,
    )
    return LoginResult(
        session_id=session_id,
        ttl_seconds=ttl_seconds,
        user=user,
        tenant=tenant,
        settings=settings,
    )


def ldap_login(
    db: Session,
    *,
    tenant_slug: str,
    username: str,
    password: str,
    ip_address: str | None = None,
) -> LoginResult:
    """Authenticate via LDAP bind when tenant auth_mode is ldap."""
    tenant = _get_tenant_by_slug(db, tenant_slug)
    settings = _get_tenant_settings(db, tenant.id)
    _ensure_sso_enabled(settings)

    if settings.auth_mode != AuthMode.LDAP:
        raise AuthError("LDAP authentication is not configured", status_code=400)

    sso_config = settings.sso_config or {}
    try:
        ldap_result: LdapAuthResult = authenticate_ldap(
            sso_config, username=username, password=password
        )
    except LdapAuthError as exc:
        write_audit_log(
            db,
            tenant_id=tenant.id,
            action="AUTH_SSO_LOGIN_FAILED",
            entity_type="user",
            entity_id=username,
            payload={"method": "ldap", "reason": str(exc)},
            ip_address=ip_address,
        )
        raise AuthError("Invalid username or password") from exc

    profile = ExternalProfile(
        external_id=ldap_result.external_id,
        email=ldap_result.email,
        display_name=ldap_result.display_name,
        dept_code=ldap_result.dept_code,
        raw_attributes=ldap_result.raw_attributes,
        provider=AuthProvider.LDAP,
    )
    user = _provision_sso_user(db, tenant, profile)
    return _complete_sso_login(
        db,
        tenant=tenant,
        settings=settings,
        user=user,
        provider=AuthProvider.LDAP,
        ip_address=ip_address,
    )


def start_oidc_login(db: Session, *, tenant_slug: str) -> SsoLoginStart:
    """Build IdP redirect URL for OIDC authorization code flow."""
    tenant = _get_tenant_by_slug(db, tenant_slug)
    settings = _get_tenant_settings(db, tenant.id)
    _ensure_sso_enabled(settings)

    if settings.auth_mode != AuthMode.OIDC:
        raise AuthError("OIDC is not configured for this tenant", status_code=400)

    sso_config = settings.sso_config or {}
    state = _store_oauth_state(tenant_slug)
    redirect_uri = oidc_redirect_uri()
    url = build_authorization_url(
        sso_config, state=state, redirect_uri=redirect_uri
    )
    return SsoLoginStart(redirect_url=url)


def complete_oidc_callback(
    db: Session,
    *,
    code: str,
    state: str,
    ip_address: str | None = None,
) -> LoginResult:
    """Handle OIDC callback and establish a Portal session."""
    tenant_slug = _pop_oauth_state(state)
    if not tenant_slug:
        raise AuthError("Invalid or expired SSO state", status_code=400)

    tenant = _get_tenant_by_slug(db, tenant_slug)
    settings = _get_tenant_settings(db, tenant.id)
    _ensure_sso_enabled(settings)

    if settings.auth_mode != AuthMode.OIDC:
        raise AuthError("OIDC is not configured", status_code=400)

    sso_config = settings.sso_config or {}
    redirect_uri = oidc_redirect_uri()

    try:
        oidc_profile: OidcProfile = exchange_code_for_profile(
            sso_config, code=code, redirect_uri=redirect_uri
        )
    except OidcAuthError as exc:
        write_audit_log(
            db,
            tenant_id=tenant.id,
            action="AUTH_SSO_LOGIN_FAILED",
            entity_type="tenant",
            entity_id=str(tenant.id),
            payload={"method": "oidc", "reason": str(exc)},
            ip_address=ip_address,
        )
        raise AuthError("SSO authentication failed") from exc

    profile = ExternalProfile(
        external_id=oidc_profile.external_id,
        email=oidc_profile.email,
        display_name=oidc_profile.display_name,
        dept_code=oidc_profile.dept_code,
        raw_attributes=oidc_profile.raw_attributes,
        provider=AuthProvider.OIDC,
    )
    user = _provision_sso_user(db, tenant, profile)
    return _complete_sso_login(
        db,
        tenant=tenant,
        settings=settings,
        user=user,
        provider=AuthProvider.OIDC,
        ip_address=ip_address,
    )


def get_login_options(db: Session, *, tenant_slug: str) -> dict[str, Any]:
    """Public login page options for a tenant."""
    tenant = _get_tenant_by_slug(db, tenant_slug)
    settings = _get_tenant_settings(db, tenant.id)
    sso_enabled = settings.sso_ldap_enabled
    auth_mode = settings.auth_mode.value

    return {
        "tenant_slug": tenant.slug,
        "tenant_name": tenant.name,
        "sso_enabled": sso_enabled,
        "auth_mode": auth_mode,
        "sso_primary": sso_enabled and auth_mode == "oidc",
        "show_local_login": not sso_enabled
        or auth_mode in ("local", "ldap"),
        "branding": settings.branding,
    }
