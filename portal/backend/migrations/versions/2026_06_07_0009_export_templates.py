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
"""Export templates table — Phase 8.

Revision ID: 0009_export_templates
Revises: 0008_provisioning_rls_entity
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_export_templates"
down_revision: Union[str, None] = "0008_provisioning_rls_entity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

template_status = postgresql.ENUM(
    "draft",
    "review",
    "published",
    "archived",
    name="template_status",
    create_type=False,
)
template_share_mode = postgresql.ENUM(
    "ALL",
    "SELECTED",
    name="template_share_mode",
    create_type=False,
)


def upgrade() -> None:
    template_status.create(op.get_bind(), checkfirst=True)
    template_share_mode.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "export_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("sql_snapshot", sa.Text(), nullable=False, server_default=""),
        sa.Column("superset_dashboard_id", sa.Integer(), nullable=True),
        sa.Column("superset_dataset_id", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            template_status,
            nullable=False,
            server_default="draft",
        ),
        sa.Column("share_mode", template_share_mode, nullable=True),
        sa.Column(
            "share_scope_version",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("reject_comment", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("published_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_export_templates_tenant_status",
        "export_templates",
        ["tenant_id", "status"],
    )
    op.create_index(
        "ix_export_templates_created_by",
        "export_templates",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_export_templates_created_by", table_name="export_templates")
    op.drop_index("ix_export_templates_tenant_status", table_name="export_templates")
    op.drop_table("export_templates")
    template_share_mode.drop(op.get_bind(), checkfirst=True)
    template_status.drop(op.get_bind(), checkfirst=True)
