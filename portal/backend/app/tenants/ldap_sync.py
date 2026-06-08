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
"""Push Portal local users into LDAP when LDAP auth is enabled."""

import uuid
from dataclasses import dataclass
from typing import Any

from ldap3 import MODIFY_REPLACE, ALL, Connection, Server
from ldap3.core.exceptions import LDAPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.password import verify_password
from app.auth.secrets import resolve_secret_ref
from app.auth.service import AuthError
from app.auth.sso_service import _upsert_identity, ExternalProfile
from app.models.tenant import AuthMode, TenantSettings
from app.models.user import SystemRole, User
from app.models.user_auth import AuthProvider


@dataclass
class LdapSyncResult:
    synced_usernames: list[str]
    skipped_usernames: list[str]


def portal_uid(username: str) -> str:
    """Map Portal username to LDAP uid (part before @)."""
    return username.strip().split("@", 1)[0].lower()


def _ldap_connection(sso_config: dict[str, Any]) -> Connection:
    ldap_uri = str(sso_config.get("ldap_uri", ""))
    bind_dn = str(sso_config.get("bind_dn", ""))
    bind_password_ref = sso_config.get("bind_password_ref")
    bind_password = resolve_secret_ref(
        str(bind_password_ref) if bind_password_ref else None
    ) or str(sso_config.get("bind_password", ""))
    user_base_dn = str(sso_config.get("user_base_dn", ""))

    if not ldap_uri or not bind_dn or not user_base_dn:
        raise AuthError("LDAP configuration is incomplete", status_code=400)

    server = Server(ldap_uri, get_info=ALL)
    conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
    return conn


def _upsert_ldap_entry(
    conn: Connection,
    *,
    user_base_dn: str,
    uid: str,
    email: str,
    display_name: str,
    plain_password: str | None,
    dept_code: str | None,
) -> None:
    user_dn = f"uid={uid},{user_base_dn}"
    conn.search(user_base_dn, f"(uid={uid})", attributes=["uid"])
    exists = bool(conn.entries)

    if exists:
        changes: dict[str, list[tuple[int, list[str]]]] = {
            "mail": [(MODIFY_REPLACE, [email])],
            "cn": [(MODIFY_REPLACE, [display_name])],
        }
        if plain_password:
            changes["userPassword"] = [(MODIFY_REPLACE, [plain_password])]
        if dept_code:
            changes["departmentNumber"] = [(MODIFY_REPLACE, [dept_code])]
        if not conn.modify(user_dn, changes):
            raise AuthError(f"LDAP update failed for {uid}: {conn.result}")
        return

    if not plain_password:
        raise AuthError(f"LDAP create for {uid} requires a password")

    attributes: dict[str, list[str]] = {
        "objectClass": ["inetOrgPerson", "organizationalPerson", "person"],
        "uid": [uid],
        "sn": [display_name.split()[0] if display_name else uid],
        "cn": [display_name],
        "mail": [email],
        "userPassword": [plain_password],
    }
    if dept_code:
        attributes["departmentNumber"] = [dept_code]

    if not conn.add(user_dn, attributes=attributes):
        raise AuthError(f"LDAP create failed for {uid}: {conn.result}")


def _dept_code_for_user(user: User) -> str | None:
    if user.system_role in (SystemRole.CNTT_CHUYENVIEN, SystemRole.CNTT_LANHDAO):
        return "CNTT"
    if user.dept_roles:
        assignment = user.dept_roles[0]
        if assignment.department is not None:
            return assignment.department.code
    return None


def sync_user_to_ldap(
    db: Session,
    *,
    user: User,
    settings: TenantSettings,
    plain_password: str | None,
    clear_local_password: bool = True,
) -> None:
    """Create or update one Portal user in LDAP (when LDAP auth is enabled)."""
    if settings.auth_mode != AuthMode.LDAP or not settings.sso_ldap_enabled:
        return

    sso_config = settings.sso_config or {}
    uid = portal_uid(user.username)
    dept_code = _dept_code_for_user(user)

    try:
        conn = _ldap_connection(sso_config)
        user_base_dn = str(sso_config["user_base_dn"])
        conn.search(user_base_dn, f"(uid={uid})", attributes=["uid"])
        exists = bool(conn.entries)
        if not exists and not plain_password:
            return
        _upsert_ldap_entry(
            conn,
            user_base_dn=user_base_dn,
            uid=uid,
            email=user.email,
            display_name=user.display_name,
            plain_password=plain_password,
            dept_code=dept_code,
        )
        profile = ExternalProfile(
            external_id=uid,
            email=user.email,
            display_name=user.display_name,
            dept_code=dept_code,
            raw_attributes={"synced_from": "portal"},
            provider=AuthProvider.LDAP,
        )
        _upsert_identity(db, user, AuthProvider.LDAP, profile)
        if clear_local_password:
            user.password_hash = None
        db.flush()
    except LDAPException as exc:
        raise AuthError(f"LDAP sync error: {exc}", status_code=502) from exc


def sync_portal_users_to_ldap(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    settings: TenantSettings,
    portal_password: str,
) -> LdapSyncResult:
    """
    Verify portal_password against each Portal user's hash; matching users
  are written to LDAP and switched to LDAP-only (password_hash cleared).
    """
    if settings.auth_mode != AuthMode.LDAP or not settings.sso_ldap_enabled:
        raise AuthError("LDAP sync requires LDAP auth mode", status_code=400)

    sso_config = settings.sso_config or {}
    users = list(
        db.scalars(
            select(User).where(
                User.tenant_id == tenant_id,
                User.password_hash.isnot(None),
            )
        )
    )
    if not users:
        raise AuthError("No Portal users with local passwords to sync", status_code=400)

    synced: list[str] = []
    skipped: list[str] = []

    try:
        conn = _ldap_connection(sso_config)
        user_base_dn = str(sso_config["user_base_dn"])

        for user in users:
            if not user.password_hash or not verify_password(
                portal_password, user.password_hash
            ):
                skipped.append(user.username)
                continue

            uid = portal_uid(user.username)
            dept = _dept_code_for_user(user)
            _upsert_ldap_entry(
                conn,
                user_base_dn=user_base_dn,
                uid=uid,
                email=user.email,
                display_name=user.display_name,
                plain_password=portal_password,
                dept_code=dept,
            )

            profile = ExternalProfile(
                external_id=uid,
                email=user.email,
                display_name=user.display_name,
                dept_code=dept,
                raw_attributes={"synced_from": "portal"},
                provider=AuthProvider.LDAP,
            )
            _upsert_identity(db, user, AuthProvider.LDAP, profile)
            user.password_hash = None
            synced.append(user.username)

    except LDAPException as exc:
        raise AuthError(f"LDAP sync error: {exc}", status_code=502) from exc

    if not synced:
        raise AuthError(
            "Portal password did not match any user. "
            "Enter the current Portal password (e.g. admin account password).",
            status_code=400,
        )

    db.flush()
    return LdapSyncResult(synced_usernames=synced, skipped_usernames=skipped)
