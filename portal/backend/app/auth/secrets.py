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
"""Resolve secret references from environment (dev) or K8s-style refs."""

import os
import re

from app.config import get_settings

_REF_ENV_MAP: dict[str, str] = {
    "secret/portal/ldap-bind": "ldap_bind_password",
    "secret/portal/keycloak-client": "oidc_client_secret",
    "secret/portal/pki/root_ca.pem": "pki_root_ca_path",
}


def resolve_secret_ref(ref: str | None) -> str | None:
    """Resolve a secret reference to a plaintext value."""
    if not ref:
        return None
    if ref.startswith("env:"):
        return os.getenv(ref[4:], "")
    if ref.startswith("k8s:"):
        # k8s:namespace/secret-name#key
        match = re.match(r"k8s:[^/]+/([^#]+)#(.+)", ref)
        if match:
            secret_name, key = match.group(1), match.group(2)
            env_key = f"{secret_name.replace('-', '_').upper()}_{key.upper()}"
            return os.getenv(env_key, "")
        return None
    mapped = _REF_ENV_MAP.get(ref)
    if mapped:
        settings = get_settings()
        return getattr(settings, mapped, None) or os.getenv(mapped.upper(), "")
    return os.getenv(ref, ref)


def mask_secret_value(value: str | None) -> str | None:
    """Return a masked placeholder when a secret is configured."""
    if value:
        return "********"
    return None
