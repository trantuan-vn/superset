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
"""Authentication business logic."""

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.audit.service import write_audit_log
from app.auth.password import verify_password
from app.auth.session import (
    clear_login_attempts,
    delete_session,
    increment_login_attempts,
)
from app.auth.session_factory import create_auth_session
from app.config import get_settings
from app.models.tenant import AuthMode, Tenant, TenantSettings
from app.models.user import SystemRole, User, UserStatus


class AuthError(Exception):
    """Base authentication error with HTTP status code."""

    def __init__(self, message: str, status_code: int = 401) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class LoginResult:
    session_id: str
    ttl_seconds: int
    user: User
    tenant: Tenant
    settings: TenantSettings
    pki_pending: bool = False


@dataclass
class MeResult:
    user: User
    tenant: Tenant
    settings: TenantSettings
    pki_pending: bool = False
    cert_serial: str | None = None


def _get_tenant_by_slug(db: Session, slug: str) -> Tenant:
    normalized = slug.strip().lower()
    tenant = db.scalar(select(Tenant).where(Tenant.slug == normalized))
    if tenant is None:
        raise AuthError("Tenant not found", status_code=404)
    return tenant


def _get_user_in_tenant(
    db: Session, tenant_id: uuid.UUID, username: str
) -> User | None:
    normalized = username.strip().lower()
    stmt = select(User).where(
        User.tenant_id == tenant_id,
        (User.username == normalized) | (User.email == normalized),
    )
    return db.scalar(stmt)


def login(
    db: Session,
    *,
    tenant_slug: str,
    username: str,
    password: str,
    ip_address: str | None = None,
) -> LoginResult:
    """Authenticate a user and create a Redis session."""
    tenant = _get_tenant_by_slug(db, tenant_slug)
    tenant_settings = db.get(TenantSettings, tenant.id)
    if tenant_settings is None:
        raise AuthError("Tenant settings not found", status_code=500)

    if (
        tenant_settings.sso_ldap_enabled
        and tenant_settings.auth_mode == AuthMode.LDAP
    ):
        from app.auth.sso_service import ldap_login

        return ldap_login(
            db,
            tenant_slug=tenant_slug,
            username=username,
            password=password,
            ip_address=ip_address,
        )

    settings = get_settings()
    user = _get_user_in_tenant(db, tenant.id, username)

    if user is None:
        increment_login_attempts(tenant_slug, username)
        write_audit_log(
            db,
            tenant_id=tenant.id,
            action="AUTH_LOGIN_FAILED",
            entity_type="user",
            entity_id=username,
            payload={"reason": "user_not_found"},
            ip_address=ip_address,
        )
        raise AuthError("Invalid username or password")

    if user.status == UserStatus.LOCKED:
        write_audit_log(
            db,
            tenant_id=tenant.id,
            action="AUTH_LOGIN_FAILED",
            entity_type="user",
            entity_id=str(user.id),
            actor_id=user.id,
            payload={"reason": "account_locked"},
            ip_address=ip_address,
        )
        raise AuthError("Account is locked. Contact your administrator.", status_code=403)

    if user.status != UserStatus.ACTIVE:
        raise AuthError("Account is inactive", status_code=403)

    if not verify_password(password, user.password_hash):
        attempts = increment_login_attempts(tenant_slug, username)
        if attempts >= settings.max_login_attempts:
            user.status = UserStatus.LOCKED
            db.commit()
            write_audit_log(
                db,
                tenant_id=tenant.id,
                action="AUTH_ACCOUNT_LOCKED",
                entity_type="user",
                entity_id=str(user.id),
                actor_id=user.id,
                payload={"attempts": attempts},
                ip_address=ip_address,
            )
            raise AuthError(
                "Account locked after too many failed attempts.",
                status_code=403,
            )
        write_audit_log(
            db,
            tenant_id=tenant.id,
            action="AUTH_LOGIN_FAILED",
            entity_type="user",
            entity_id=str(user.id),
            actor_id=user.id,
            payload={"reason": "invalid_password", "attempts": attempts},
            ip_address=ip_address,
        )
        raise AuthError("Invalid username or password")

    clear_login_attempts(tenant_slug, username)
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()

    session_id, ttl_seconds, pki_pending = create_auth_session(
        user.id, tenant.id, tenant_settings
    )

    write_audit_log(
        db,
        tenant_id=tenant.id,
        action="AUTH_LOGIN",
        entity_type="user",
        entity_id=str(user.id),
        actor_id=user.id,
        payload={"method": "local", "pki_pending": pki_pending},
        ip_address=ip_address,
    )

    return LoginResult(
        session_id=session_id,
        ttl_seconds=ttl_seconds,
        user=user,
        tenant=tenant,
        settings=tenant_settings,
        pki_pending=pki_pending,
    )


def logout(
    db: Session,
    *,
    session_id: str,
    user: User,
    ip_address: str | None = None,
) -> None:
    """Destroy session and write audit log."""
    delete_session(session_id)
    write_audit_log(
        db,
        tenant_id=user.tenant_id,
        action="AUTH_LOGOUT",
        entity_type="user",
        entity_id=str(user.id),
        actor_id=user.id,
        ip_address=ip_address,
    )


def get_me(
    db: Session,
    user_id: uuid.UUID,
    *,
    pki_pending: bool = False,
    cert_serial: str | None = None,
) -> MeResult:
    """Load current user with tenant context."""
    stmt = (
        select(User)
        .options(joinedload(User.tenant).joinedload(Tenant.settings))
        .where(User.id == user_id)
    )
    user = db.scalar(stmt)
    if user is None:
        raise AuthError("User not found", status_code=404)
    if user.status != UserStatus.ACTIVE:
        raise AuthError("Account is inactive", status_code=403)

    tenant_settings = user.tenant.settings
    if tenant_settings is None:
        raise AuthError("Tenant settings not found", status_code=500)

    return MeResult(
        user=user,
        tenant=user.tenant,
        settings=tenant_settings,
        pki_pending=pki_pending,
        cert_serial=cert_serial,
    )
