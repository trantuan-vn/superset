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
"""Baseline tenants and tenant_settings tables — Phase 0.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

tenant_status = postgresql.ENUM(
    "active", "suspended", "archived", name="tenant_status", create_type=False
)
auth_mode = postgresql.ENUM(
    "local", "oidc", "saml", "ldap", name="auth_mode", create_type=False
)


def upgrade() -> None:
    tenant_status.create(op.get_bind(), checkfirst=True)
    auth_mode.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            tenant_status,
            nullable=False,
            server_default="active",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
    )

    op.create_table(
        "tenant_settings",
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "sso_ldap_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "auth_mode",
            auth_mode,
            nullable=False,
            server_default="local",
        ),
        sa.Column("sso_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "digital_signature_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("pki_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "ai_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("ai_config", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "export_formats",
            postgresql.ARRAY(sa.Text()),
            nullable=True,
        ),
        sa.Column(
            "download_token_ttl_hours",
            sa.Integer(),
            nullable=False,
            server_default="24",
        ),
        sa.Column("branding", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("tenant_id"),
    )


def downgrade() -> None:
    op.drop_table("tenant_settings")
    op.drop_table("tenants")
    auth_mode.drop(op.get_bind(), checkfirst=True)
    tenant_status.drop(op.get_bind(), checkfirst=True)
