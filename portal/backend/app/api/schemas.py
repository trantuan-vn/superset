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


class UserDeptRoleResponse(BaseModel):
    department_id: str
    department_code: str
    department_name: str
    role: str


class UserResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    system_role: str
    departments: list[UserDeptRoleResponse] = Field(default_factory=list)


class TenantBrandingResponse(BaseModel):
    app_name: str | None = None
    logo_url: str | None = None
    primary_color: str | None = None
    favicon_url: str | None = None


class TenantResponse(BaseModel):
    id: str
    slug: str
    name: str
    ai_enabled: bool = False
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


class ProvisioningSummaryResponse(BaseModel):
    status: str
    message: str | None = None


class DepartmentResponse(BaseModel):
    id: str
    tenant_id: str
    code: str
    name: str
    status: str
    provisioning: ProvisioningSummaryResponse | None = None


class ProvisioningLogResponse(BaseModel):
    id: str
    entity_type: str
    entity_key: str
    operation: str
    superset_id: int | None = None
    status: str
    error_message: str | None = None
    attempts: int
    updated_at: str


class ProvisioningStatusResponse(BaseModel):
    enabled: bool
    superset_reachable: bool
    logs: list[ProvisioningLogResponse] = Field(default_factory=list)


class CreateDepartmentRequest(BaseModel):
    code: str = Field(..., min_length=2, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)


class UpdateDepartmentRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    status: str | None = None


class UserAdminResponse(BaseModel):
    id: str
    username: str
    email: str
    display_name: str
    system_role: str
    status: str
    departments: list[UserDeptRoleResponse] = Field(default_factory=list)


class CreateUserRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=128)
    email: str = Field(..., min_length=3, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=8, max_length=256)
    system_role: str = Field(..., description="dept_user, cntt_chuyenvien, cntt_lanhdao, tenant_admin")


class UpdateUserRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    email: str | None = Field(default=None, min_length=3, max_length=255)
    status: str | None = None


class AssignDeptRoleRequest(BaseModel):
    department_id: str
    role: str = Field(..., description="chuyenvien or lanhdao")


class GenerateSqlRequest(BaseModel):
    prompt: str = Field(..., min_length=3, max_length=4000)
    context_sql: str | None = Field(default=None, max_length=32000)
    dataset_hint: str | None = Field(default=None, max_length=128)


class GenerateSqlResponse(BaseModel):
    sql: str


class McpTokenResponse(BaseModel):
    token: str
    expires_in_seconds: int
    superset_username: str


def branding_from_json(raw: dict[str, Any] | None) -> TenantBrandingResponse | None:
    if not raw:
        return None
    return TenantBrandingResponse(
        app_name=raw.get("app_name"),
        logo_url=raw.get("logo_url"),
        primary_color=raw.get("primary_color"),
        favicon_url=raw.get("favicon_url"),
    )
