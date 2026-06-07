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
"""Tenant settings management — Phase 2."""

import copy
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import write_audit_log
from app.auth.pki_ca import (
    mask_pki_config_for_api,
    pki_has_trusted_ca,
    remove_ca_from_pki_config,
    store_ca_in_pki_config,
)
from app.auth.pki_verify import PkiVerifyError
from app.auth.secrets import mask_secret_value, resolve_secret_ref
from app.auth.service import AuthError
from app.models.tenant import AuthMode, TenantSettings
from app.models.user import User
from app.tenants.ldap_sync import sync_portal_users_to_ldap


def count_local_password_users(db: Session, tenant_id: uuid.UUID) -> int:
    """Portal users not yet migrated to LDAP (still have password_hash)."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.tenant_id == tenant_id,
                User.password_hash.isnot(None),
            )
        )
        or 0
    )


def count_sso_only_users(db: Session, tenant_id: uuid.UUID) -> int:
    """Portal users without a local password (LDAP/OIDC-only)."""
    return int(
        db.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.tenant_id == tenant_id,
                User.password_hash.is_(None),
            )
        )
        or 0
    )


def ldap_migration_required(db: Session, settings: TenantSettings) -> bool:
    if not settings.sso_ldap_enabled or settings.auth_mode != AuthMode.LDAP:
        return False
    return count_local_password_users(db, settings.tenant_id) > 0

_SECRET_KEYS = ("bind_password", "client_secret", "bind_password_ref", "client_secret_ref")


def _mask_ai_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    if not config:
        return None
    masked = copy.deepcopy(config)
    if masked.get("api_key") or masked.get("api_key_ref"):
        masked["api_key_set"] = True
    if "api_key" in masked:
        masked["api_key"] = mask_secret_value(str(masked["api_key"])) or "********"
    return masked


def _mask_sso_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    if not config:
        return None
    masked = copy.deepcopy(config)
    bind_ref = masked.get("bind_password_ref")
    secret_ref = masked.get("client_secret_ref")
    bind_plain = masked.get("bind_password")
    secret_plain = masked.get("client_secret")

    if bind_ref or bind_plain or resolve_secret_ref(str(bind_ref) if bind_ref else None):
        masked["bind_password_set"] = True
    if secret_ref or secret_plain or resolve_secret_ref(str(secret_ref) if secret_ref else None):
        masked["client_secret_set"] = True

    for key in ("bind_password", "client_secret"):
        if key in masked:
            masked[key] = mask_secret_value(str(masked[key])) or "********"

    return masked


def get_tenant_settings(db: Session, tenant_id: uuid.UUID) -> TenantSettings:
    settings = db.get(TenantSettings, tenant_id)
    if settings is None:
        raise AuthError("Tenant settings not found", status_code=404)
    return settings


def settings_to_response(
    settings: TenantSettings, *, db: Session | None = None
) -> dict[str, Any]:
    migration_required = (
        ldap_migration_required(db, settings) if db is not None else False
    )
    return {
        "tenant_id": str(settings.tenant_id),
        "sso_ldap_enabled": settings.sso_ldap_enabled,
        "auth_mode": settings.auth_mode.value,
        "ldap_migration_required": migration_required,
        "sso_config": _mask_sso_config(settings.sso_config),
        "digital_signature_enabled": settings.digital_signature_enabled,
        "pki_config": mask_pki_config_for_api(settings.pki_config),
        "ai_enabled": settings.ai_enabled,
        "ai_config": _mask_ai_config(settings.ai_config),
        "export_formats": settings.export_formats,
        "download_token_ttl_hours": settings.download_token_ttl_hours,
        "branding": settings.branding,
    }


def update_tenant_settings(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor: User,
    patch: dict[str, Any],
    ip_address: str | None = None,
) -> TenantSettings:
    """Patch tenant settings; merge sso_config without overwriting secrets."""
    settings = get_tenant_settings(db, tenant_id)
    portal_password = patch.pop("portal_password", None)

    if "sso_ldap_enabled" in patch:
        enabling_sso = bool(patch["sso_ldap_enabled"])
        if not enabling_sso and settings.sso_ldap_enabled:
            if count_sso_only_users(db, tenant_id) > 0:
                raise AuthError(
                    "Cannot disable SSO while users authenticate via LDAP/OIDC only. "
                    "Keep SSO enabled or reset user passwords first.",
                    status_code=400,
                )
            settings.auth_mode = AuthMode.LOCAL
        settings.sso_ldap_enabled = enabling_sso

    if "auth_mode" in patch and patch["auth_mode"]:
        if settings.sso_ldap_enabled:
            settings.auth_mode = AuthMode(patch["auth_mode"])
        else:
            settings.auth_mode = AuthMode.LOCAL

    if "digital_signature_enabled" in patch:
        enabling = bool(patch["digital_signature_enabled"])
        if enabling and not pki_has_trusted_ca(settings.pki_config):
            raise AuthError(
                "Upload a root CA certificate before enabling PKI",
                status_code=400,
            )
        settings.digital_signature_enabled = enabling

    if "ai_enabled" in patch:
        enabling_ai = bool(patch["ai_enabled"])
        if enabling_ai and not settings.ai_config:
            settings.ai_config = {"provider": "mock"}
        settings.ai_enabled = enabling_ai

    if "branding" in patch:
        settings.branding = patch["branding"]

    if "sso_config" in patch and patch["sso_config"] is not None:
        incoming: dict[str, Any] = patch["sso_config"]
        merged = copy.deepcopy(settings.sso_config or {})
        for key, value in incoming.items():
            if key in ("bind_password", "client_secret") and not value:
                continue
            if value is not None:
                merged[key] = value
        settings.sso_config = merged

    if "pki_config" in patch and patch["pki_config"] is not None:
        merged_pki = copy.deepcopy(settings.pki_config or {})
        for key, value in patch["pki_config"].items():
            if key in (
                "ca_certificate_pem",
                "ca_subject_dn",
                "ca_fingerprint",
                "ca_uploaded_at",
            ):
                continue
            if value is not None:
                merged_pki[key] = value
        settings.pki_config = merged_pki

    if "ai_config" in patch and patch["ai_config"] is not None:
        merged_ai = copy.deepcopy(settings.ai_config or {})
        for key, value in patch["ai_config"].items():
            if key == "api_key" and not value:
                continue
            if value is not None:
                merged_ai[key] = value
        settings.ai_config = merged_ai

    will_be_ldap = settings.sso_ldap_enabled and settings.auth_mode == AuthMode.LDAP
    needs_migration = will_be_ldap and count_local_password_users(db, tenant_id) > 0

    if will_be_ldap and settings.sso_config:
        if needs_migration and not portal_password:
            raise AuthError(
                "portal_password is required to migrate Portal users into LDAP. "
                "Enter the current Portal password (e.g. your admin password).",
                status_code=400,
            )
        if portal_password:
            sync_result = sync_portal_users_to_ldap(
                db,
                tenant_id=tenant_id,
                settings=settings,
                portal_password=str(portal_password),
            )
            write_audit_log(
                db,
                tenant_id=tenant_id,
                action="LDAP_PORTAL_USERS_SYNCED",
                entity_type="tenant",
                entity_id=str(tenant_id),
                actor_id=actor.id,
                payload={
                    "synced": sync_result.synced_usernames,
                    "skipped": sync_result.skipped_usernames,
                },
                ip_address=ip_address,
            )

    db.commit()
    db.refresh(settings)

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="TENANT_SETTINGS_UPDATED",
        entity_type="tenant_settings",
        entity_id=str(tenant_id),
        actor_id=actor.id,
        payload={
            "sso_ldap_enabled": settings.sso_ldap_enabled,
            "auth_mode": settings.auth_mode.value,
            "digital_signature_enabled": settings.digital_signature_enabled,
        },
        ip_address=ip_address,
    )
    return settings


def upload_tenant_ca_certificate(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor: User,
    certificate_pem: str,
    ip_address: str | None = None,
) -> TenantSettings:
    """Store tenant root CA PEM in tenant_settings.pki_config."""
    settings = get_tenant_settings(db, tenant_id)
    try:
        settings.pki_config = store_ca_in_pki_config(
            settings.pki_config, certificate_pem=certificate_pem
        )
    except PkiVerifyError as exc:
        raise AuthError(str(exc), status_code=400) from exc

    db.commit()
    db.refresh(settings)

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="PKI_CA_UPLOADED",
        entity_type="tenant_settings",
        entity_id=str(tenant_id),
        actor_id=actor.id,
        payload={
            "ca_fingerprint": settings.pki_config.get("ca_fingerprint"),
            "ca_subject_dn": settings.pki_config.get("ca_subject_dn"),
        },
        ip_address=ip_address,
    )
    return settings


def remove_tenant_ca_certificate(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor: User,
    ip_address: str | None = None,
) -> TenantSettings:
    """Remove uploaded root CA; disables PKI if no other trust source exists."""
    settings = get_tenant_settings(db, tenant_id)
    settings.pki_config = remove_ca_from_pki_config(settings.pki_config)
    if settings.digital_signature_enabled and not pki_has_trusted_ca(settings.pki_config):
        settings.digital_signature_enabled = False

    db.commit()
    db.refresh(settings)

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="PKI_CA_REMOVED",
        entity_type="tenant_settings",
        entity_id=str(tenant_id),
        actor_id=actor.id,
        payload={},
        ip_address=ip_address,
    )
    return settings


def upload_tenant_ca_certificate(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor: User,
    certificate_pem: str,
    ip_address: str | None = None,
) -> TenantSettings:
    """Store tenant root CA PEM in tenant_settings.pki_config."""
    settings = get_tenant_settings(db, tenant_id)
    try:
        settings.pki_config = store_ca_in_pki_config(
            settings.pki_config, certificate_pem=certificate_pem
        )
    except PkiVerifyError as exc:
        raise AuthError(str(exc), status_code=400) from exc

    db.commit()
    db.refresh(settings)

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="PKI_CA_UPLOADED",
        entity_type="tenant_settings",
        entity_id=str(tenant_id),
        actor_id=actor.id,
        payload={
            "ca_fingerprint": settings.pki_config.get("ca_fingerprint"),
            "ca_subject_dn": settings.pki_config.get("ca_subject_dn"),
        },
        ip_address=ip_address,
    )
    return settings


def remove_tenant_ca_certificate(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    actor: User,
    ip_address: str | None = None,
) -> TenantSettings:
    """Remove uploaded root CA; disables PKI if no other trust source exists."""
    settings = get_tenant_settings(db, tenant_id)
    settings.pki_config = remove_ca_from_pki_config(settings.pki_config)
    if settings.digital_signature_enabled and not pki_has_trusted_ca(settings.pki_config):
        settings.digital_signature_enabled = False

    db.commit()
    db.refresh(settings)

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="PKI_CA_REMOVED",
        entity_type="tenant_settings",
        entity_id=str(tenant_id),
        actor_id=actor.id,
        payload={},
        ip_address=ip_address,
    )
    return settings
