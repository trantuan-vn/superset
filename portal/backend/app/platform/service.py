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
"""Platform operator — create tenants and tenant administrators."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.auth.password import hash_password
from app.auth.service import AuthError
from app.models.tenant import Tenant, TenantSettings, TenantStatus
from app.models.user import SystemRole, User, UserStatus


@dataclass
class TenantSummary:
    id: uuid.UUID
    slug: str
    name: str
    status: str
    admin_count: int
    pki_enabled: bool


@dataclass
class CreateTenantResult:
    tenant: Tenant
    admin_user: User


def list_tenants(db: Session) -> list[TenantSummary]:
    """List business tenants (excludes platform operator tenant)."""
    stmt = (
        select(
            Tenant,
            func.count(User.id).filter(User.system_role == SystemRole.TENANT_ADMIN),
        )
        .outerjoin(User, User.tenant_id == Tenant.id)
        .where(Tenant.slug != "platform")
        .group_by(Tenant.id)
        .order_by(Tenant.slug)
    )
    rows = db.execute(stmt).all()
    result: list[TenantSummary] = []
    for tenant, admin_count in rows:
        settings = tenant.settings
        result.append(
            TenantSummary(
                id=tenant.id,
                slug=tenant.slug,
                name=tenant.name,
                status=tenant.status.value,
                admin_count=int(admin_count or 0),
                pki_enabled=bool(settings and settings.digital_signature_enabled),
            )
        )
    return result


def create_tenant_with_admin(
    db: Session,
    *,
    slug: str,
    name: str,
    admin_email: str,
    admin_password: str,
    admin_display_name: str,
    actor_id: uuid.UUID,
    ip_address: str | None = None,
) -> CreateTenantResult:
    """Onboard a new tenant and its first tenant_admin user."""
    normalized_slug = slug.strip().lower()
    if not normalized_slug or " " in normalized_slug:
        raise AuthError("Invalid tenant slug", status_code=400)
    if normalized_slug == "platform":
        raise AuthError("Reserved tenant slug", status_code=400)

    existing = db.scalar(select(Tenant).where(Tenant.slug == normalized_slug))
    if existing is not None:
        raise AuthError("Tenant slug already exists", status_code=409)

    tenant = Tenant(slug=normalized_slug, name=name.strip(), status=TenantStatus.ACTIVE)
    db.add(tenant)
    db.flush()

    settings = TenantSettings(
        tenant_id=tenant.id,
        branding={"app_name": f"Portal — {name.strip()}"},
    )
    db.add(settings)

    email = admin_email.strip().lower()
    admin = User(
        tenant_id=tenant.id,
        username=email,
        email=email,
        display_name=admin_display_name.strip(),
        password_hash=hash_password(admin_password),
        system_role=SystemRole.TENANT_ADMIN,
        status=UserStatus.ACTIVE,
    )
    db.add(admin)
    db.commit()
    db.refresh(tenant)
    db.refresh(admin)

    write_audit_log(
        db,
        tenant_id=tenant.id,
        action="TENANT_CREATED",
        entity_type="tenant",
        entity_id=str(tenant.id),
        actor_id=actor_id,
        payload={"slug": tenant.slug, "admin_email": email},
        ip_address=ip_address,
    )
    return CreateTenantResult(tenant=tenant, admin_user=admin)


def add_tenant_admin(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    admin_email: str,
    admin_password: str,
    admin_display_name: str,
    actor_id: uuid.UUID,
    ip_address: str | None = None,
) -> User:
    """Assign an additional tenant_admin to an existing business tenant."""
    tenant = db.get(Tenant, tenant_id)
    if tenant is None or tenant.slug == "platform":
        raise AuthError("Tenant not found", status_code=404)

    email = admin_email.strip().lower()
    existing = db.scalar(
        select(User).where(User.tenant_id == tenant_id, User.email == email)
    )
    if existing is not None:
        raise AuthError("User already exists in this tenant", status_code=409)

    admin = User(
        tenant_id=tenant_id,
        username=email,
        email=email,
        display_name=admin_display_name.strip(),
        password_hash=hash_password(admin_password),
        system_role=SystemRole.TENANT_ADMIN,
        status=UserStatus.ACTIVE,
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="TENANT_ADMIN_ADDED",
        entity_type="user",
        entity_id=str(admin.id),
        actor_id=actor_id,
        payload={"email": email},
        ip_address=ip_address,
    )
    return admin
