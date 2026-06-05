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


class MessageResponse(BaseModel):
    message: str


def branding_from_json(raw: dict[str, Any] | None) -> TenantBrandingResponse | None:
    if not raw:
        return None
    return TenantBrandingResponse(
        app_name=raw.get("app_name"),
        logo_url=raw.get("logo_url"),
        primary_color=raw.get("primary_color"),
        favicon_url=raw.get("favicon_url"),
    )
