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
"""Tenant and tenant_settings models — Phase 0 baseline schema."""

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.models.user import User

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class TenantStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    ARCHIVED = "archived"


class AuthMode(str, enum.Enum):
    LOCAL = "local"
    OIDC = "oidc"
    SAML = "saml"
    LDAP = "ldap"


class Tenant(Base):
    __tablename__ = "tenants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[TenantStatus] = mapped_column(
        Enum(
            TenantStatus,
            name="tenant_status",
            native_enum=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=TenantStatus.ACTIVE,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    settings: Mapped["TenantSettings"] = relationship(
        "TenantSettings", back_populates="tenant", uselist=False
    )
    users: Mapped[list["User"]] = relationship("User", back_populates="tenant")


class TenantSettings(Base):
    __tablename__ = "tenant_settings"

    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sso_ldap_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    auth_mode: Mapped[AuthMode] = mapped_column(
        Enum(
            AuthMode,
            name="auth_mode",
            native_enum=True,
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=AuthMode.LOCAL,
    )
    sso_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    digital_signature_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    pki_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ai_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ai_config: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    export_formats: Mapped[list[str] | None] = mapped_column(
        ARRAY(Text), nullable=True
    )
    download_token_ttl_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, default=24
    )
    branding: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="settings")
