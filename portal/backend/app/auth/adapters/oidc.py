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
"""OpenID Connect adapter (Keycloak-compatible)."""

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.auth.secrets import resolve_secret_ref
from app.config import get_settings


class OidcAuthError(Exception):
    """OIDC flow failed."""


@dataclass
class OidcProfile:
    external_id: str
    email: str
    display_name: str
    dept_code: str | None
    raw_attributes: dict[str, Any]


@dataclass
class OidcDiscovery:
    authorization_endpoint: str
    token_endpoint: str
    userinfo_endpoint: str | None


def fetch_oidc_discovery(issuer_url: str) -> OidcDiscovery:
    """Load OIDC discovery document from issuer."""
    issuer = issuer_url.rstrip("/")
    url = f"{issuer}/.well-known/openid-configuration"
    try:
        response = httpx.get(url, timeout=10.0)
        response.raise_for_status()
        data = response.json()
    except httpx.HTTPError as exc:
        raise OidcAuthError(f"OIDC discovery failed: {exc}") from exc

    auth_ep = data.get("authorization_endpoint")
    token_ep = data.get("token_endpoint")
    if not auth_ep or not token_ep:
        raise OidcAuthError("Invalid OIDC discovery document")

    return OidcDiscovery(
        authorization_endpoint=str(auth_ep),
        token_endpoint=str(token_ep),
        userinfo_endpoint=data.get("userinfo_endpoint"),
    )


def build_authorization_url(
    sso_config: dict[str, Any],
    *,
    state: str,
    redirect_uri: str,
) -> str:
    """Build the IdP authorization redirect URL."""
    issuer_url = str(sso_config.get("issuer_url", ""))
    client_id = str(sso_config.get("client_id", ""))
    scopes = sso_config.get("scopes") or ["openid", "profile", "email"]
    scope_str = " ".join(scopes)

    discovery = fetch_oidc_discovery(issuer_url)
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope_str,
        "state": state,
    }
    return f"{discovery.authorization_endpoint}?{urlencode(params)}"


def exchange_code_for_profile(
    sso_config: dict[str, Any],
    *,
    code: str,
    redirect_uri: str,
) -> OidcProfile:
    """Exchange authorization code for tokens and load user profile."""
    issuer_url = str(sso_config.get("issuer_url", ""))
    client_id = str(sso_config.get("client_id", ""))
    secret_ref = sso_config.get("client_secret_ref")
    client_secret = resolve_secret_ref(
        str(secret_ref) if secret_ref else None
    ) or str(sso_config.get("client_secret", ""))

    discovery = fetch_oidc_discovery(issuer_url)
    token_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    try:
        token_response = httpx.post(
            discovery.token_endpoint,
            data=token_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=15.0,
        )
        token_response.raise_for_status()
        tokens = token_response.json()
    except httpx.HTTPError as exc:
        raise OidcAuthError(f"Token exchange failed: {exc}") from exc

    profile: dict[str, Any] = {}
    if discovery.userinfo_endpoint and tokens.get("access_token"):
        try:
            ui_response = httpx.get(
                discovery.userinfo_endpoint,
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=10.0,
            )
            ui_response.raise_for_status()
            profile = ui_response.json()
        except httpx.HTTPError:
            profile = {}

    if not profile and tokens.get("id_token"):
        profile = _decode_id_token_payload(str(tokens["id_token"]))

    mapping: dict[str, str] = sso_config.get("attribute_mapping") or {}
    external_key = mapping.get("external_id", "sub")
    email_key = mapping.get("email", "email")
    display_key = mapping.get("display_name", "name")
    dept_key = mapping.get("dept_code", "department")

    external_id = str(profile.get(external_key, ""))
    if not external_id:
        raise OidcAuthError("Missing subject in OIDC profile")

    email = str(profile.get(email_key, "") or profile.get("preferred_username", ""))
    display_name = str(
        profile.get(display_key, "") or profile.get("preferred_username", external_id)
    )
    dept_raw = profile.get(dept_key)
    dept_code: str | None = None
    if isinstance(dept_raw, list) and dept_raw:
        dept_code = str(dept_raw[0])
    elif dept_raw:
        dept_code = str(dept_raw)

    return OidcProfile(
        external_id=external_id,
        email=email or f"{external_id}@oidc.local",
        display_name=display_name,
        dept_code=dept_code,
        raw_attributes=profile,
    )


def _decode_id_token_payload(id_token: str) -> dict[str, Any]:
    """Decode JWT payload without signature verification (dev fallback)."""
    import base64
    import json

    parts = id_token.split(".")
    if len(parts) < 2:
        return {}
    payload = parts[1]
    padding = "=" * (-len(payload) % 4)
    try:
        decoded = base64.urlsafe_b64decode(payload + padding)
        return json.loads(decoded)
    except (ValueError, json.JSONDecodeError):
        return {}


def oidc_redirect_uri() -> str:
    settings = get_settings()
    return f"{settings.portal_public_base_url.rstrip('/')}/auth/sso/callback"
