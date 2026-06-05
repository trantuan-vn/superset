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
"""Users, audit_logs tables and demo seed — Phase 1.

Revision ID: 0002_users_audit
Revises: 0001_baseline
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_users_audit"
down_revision: Union[str, None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

system_role = postgresql.ENUM(
    "tenant_admin",
    "cntt_chuyenvien",
    "cntt_lanhdao",
    "dept_user",
    name="system_role",
    create_type=False,
)
user_status = postgresql.ENUM(
    "active", "inactive", "locked", name="user_status", create_type=False
)

def upgrade() -> None:
    system_role.create(op.get_bind(), checkfirst=True)
    user_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("username", sa.String(length=128), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("system_role", system_role, nullable=False),
        sa.Column(
            "status",
            user_status,
            nullable=False,
            server_default="active",
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "username", name="uq_users_tenant_username"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=False),
        sa.Column("entity_id", sa.String(length=128), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("ip_address", postgresql.INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_tenant_id", "audit_logs", ["tenant_id"])
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])

    # Demo tenant + users (idempotent via ON CONFLICT)
    conn = op.get_bind()
    conn.execute(
        sa.text(
            """
            INSERT INTO tenants (id, slug, name, status)
            VALUES (
                'a0000000-0000-4000-8000-000000000001',
                'demo-corp',
                'Demo Corporation',
                'active'
            )
            ON CONFLICT (slug) DO NOTHING
            """
        )
    )
    conn.execute(
        sa.text(
            """
            INSERT INTO tenant_settings (tenant_id, branding)
            VALUES (
                'a0000000-0000-4000-8000-000000000001',
                '{"app_name": "Portal Kết xuất", "primary_color": "#1677ff"}'::jsonb
            )
            ON CONFLICT (tenant_id) DO NOTHING
            """
        )
    )

def downgrade() -> None:
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_tenant_id", table_name="audit_logs")
    op.drop_table("audit_logs")
    op.drop_index("ix_users_tenant_id", table_name="users")
    op.drop_table("users")
    user_status.drop(op.get_bind(), checkfirst=True)
    system_role.drop(op.get_bind(), checkfirst=True)
