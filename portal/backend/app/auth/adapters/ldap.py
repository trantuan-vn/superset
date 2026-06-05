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
"""LDAP bind authentication adapter."""

from dataclasses import dataclass
from typing import Any

from ldap3 import ALL, Connection, Server
from ldap3.core.exceptions import LDAPException

from app.auth.secrets import resolve_secret_ref
from app.auth.serialize import json_safe_attributes


class LdapAuthError(Exception):
    """LDAP authentication failed."""


@dataclass
class LdapAuthResult:
    external_id: str
    email: str
    display_name: str
    dept_code: str | None
    raw_attributes: dict[str, Any]


def _get_attr(entry: Any, name: str) -> str | None:
    if not hasattr(entry, name):
        return None
    value = getattr(entry, name)
    if value is None:
        return None
    if isinstance(value, list):
        return str(value[0]) if value else None
    return str(value)


def authenticate_ldap(
    sso_config: dict[str, Any],
    *,
    username: str,
    password: str,
) -> LdapAuthResult:
    """Bind to LDAP with service account, search user, verify password."""
    ldap_uri = str(sso_config.get("ldap_uri", ""))
    bind_dn = str(sso_config.get("bind_dn", ""))
    bind_password_ref = sso_config.get("bind_password_ref")
    bind_password = resolve_secret_ref(
        str(bind_password_ref) if bind_password_ref else None
    ) or str(sso_config.get("bind_password", ""))
    user_base_dn = str(sso_config.get("user_base_dn", ""))
    user_filter_template = str(sso_config.get("user_filter", "(uid={username})"))
    mapping: dict[str, str] = sso_config.get("attribute_mapping") or {}

    if not ldap_uri or not user_base_dn:
        raise LdapAuthError("LDAP configuration is incomplete")

    uid = username.strip()
    if "@" in uid:
        uid = uid.split("@", 1)[0]

    user_filter = user_filter_template.format(username=uid)

    try:
        server = Server(ldap_uri, get_info=ALL)
        conn = Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
        if not conn.search(user_base_dn, user_filter, attributes=["*"]):
            raise LdapAuthError("User not found in directory")

        entry = conn.entries[0]
        user_dn = str(entry.entry_dn)

        user_conn = Connection(server, user=user_dn, password=password, auto_bind=True)
        if not user_conn.bind():
            raise LdapAuthError("Invalid credentials")

        external_key = mapping.get("external_id", "uid")
        email_key = mapping.get("email", "mail")
        display_key = mapping.get("display_name", "cn")
        dept_key = mapping.get("dept_code", "departmentNumber")

        external_id = _get_attr(entry, external_key) or uid
        email = _get_attr(entry, email_key) or f"{uid}@local"
        display_name = _get_attr(entry, display_key) or uid
        dept_code = _get_attr(entry, dept_key)

        raw: dict[str, Any] = {}
        if hasattr(entry, "entry_attributes_as_dict"):
            raw = json_safe_attributes(dict(entry.entry_attributes_as_dict))

        return LdapAuthResult(
            external_id=external_id,
            email=email,
            display_name=display_name,
            dept_code=dept_code,
            raw_attributes=raw,
        )
    except LdapAuthError:
        raise
    except LDAPException as exc:
        raise LdapAuthError(f"LDAP error: {exc}") from exc
