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
"""Pydantic schemas for API request/response bodies."""

from typing import Any

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    tenant_slug: str = Field(..., min_length=1, max_length=128)
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=256)


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    system_role: str


class TenantBrandingResponse(BaseModel):
    app_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    favicon_url: str | None = None


class TenantResponse(BaseModel):
    id: str
    slug: str
    name: str
    branding: TenantBrandingResponse | None = None


class MeResponse(BaseModel):
    user: UserResponse
    tenant: TenantResponse
    pki_pending: bool = False
    cert_serial: str | None = None


class MessageResponse(BaseModel):
    message: str


class LoginOptionsResponse(BaseModel):
    tenant_slug: str
    tenant_name: str
    sso_enabled: bool
    auth_mode: str
    sso_primary: bool
    show_local_login: bool
    pki_enabled: bool = False
    branding: TenantBrandingResponse | None = None


class PkiChallengeResponse(BaseModel):
    nonce: str
    expires_in_seconds: int


class PkiVerifyRequest(BaseModel):
    certificate: str = Field(..., min_length=64, description="PEM-encoded X.509 certificate")
    signature: str = Field(..., min_length=1, description="Base64 signature over nonce")


class PkiVerifyResponse(BaseModel):
    cert_serial: str
    subject_dn: str
    message: str = "PKI verification successful"


class TenantSettingsResponse(BaseModel):
    tenant_id: str
    sso_ldap_enabled: bool
    auth_mode: str
    ldap_migration_required: bool = False
    sso_config: dict[str, Any] | None = None
    digital_signature_enabled: bool
    pki_config: dict[str, Any] | None = None
    ai_enabled: bool
    ai_config: dict[str, Any] | None = None
    export_formats: list[str] | None = None
    download_token_ttl_hours: int
    branding: dict[str, Any] | None = None


class PkiCaUploadRequest(BaseModel):
    certificate: str = Field(
        ...,
        min_length=64,
        description="PEM-encoded root CA certificate (root_ca.crt)",
    )


class PlatformTenantResponse(BaseModel):
    id: str
    slug: str
    name: str
    status: str
    admin_count: int
    pki_enabled: bool


class TenantAdminResponse(BaseModel):
    id: str
    email: str
    display_name: str


class CreateTenantRequest(BaseModel):
    slug: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    admin_email: str = Field(..., min_length=3, max_length=255)
    admin_password: str = Field(..., min_length=8, max_length=256)
    admin_display_name: str = Field(..., min_length=1, max_length=255)


class CreateTenantAdminRequest(BaseModel):
    admin_email: str = Field(..., min_length=3, max_length=255)
    admin_password: str = Field(..., min_length=8, max_length=256)
    admin_display_name: str = Field(..., min_length=1, max_length=255)


class CreateTenantResponse(BaseModel):
    tenant: PlatformTenantResponse
    admin: TenantAdminResponse


class TenantSettingsPatch(BaseModel):
    sso_ldap_enabled: bool | None = None
    auth_mode: str | None = None
    sso_config: dict[str, Any] | None = None
    digital_signature_enabled: bool | None = None
    pki_config: dict[str, Any] | None = None
    ai_enabled: bool | None = None
    ai_config: dict[str, Any] | None = None
    branding: dict[str, Any] | None = None
    portal_password: str | None = Field(
        default=None,
        min_length=1,
        max_length=256,
        description="Current Portal password — used once to verify and push users into LDAP",
    )


def branding_from_json(raw: dict[str, Any] | None) -> TenantBrandingResponse | None:
    if not raw:
        return None
    return TenantBrandingResponse(
        app_name=raw.get("app_name"),
        logo_url=raw.get("logo_url"),
        primary_color=raw.get("primary_color"),
        favicon_url=raw.get("favicon_url"),
    )
