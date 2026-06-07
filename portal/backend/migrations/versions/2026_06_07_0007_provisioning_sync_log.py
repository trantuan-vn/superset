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
"""Provisioning sync log table — Phase 5.

Revision ID: 0007_provisioning_sync_log
Revises: 0006_departments
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007_provisioning_sync_log"
down_revision: Union[str, None] = "0006_departments"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

provisioning_entity_type = postgresql.ENUM(
    "role",
    "user",
    name="provisioning_entity_type",
    create_type=False,
)
provisioning_operation = postgresql.ENUM(
    "create",
    "update",
    "deactivate",
    name="provisioning_operation",
    create_type=False,
)
provisioning_sync_status = postgresql.ENUM(
    "pending",
    "success",
    "failed",
    "dead_letter",
    "skipped",
    name="provisioning_sync_status",
    create_type=False,
)


def upgrade() -> None:
    provisioning_entity_type.create(op.get_bind(), checkfirst=True)
    provisioning_operation.create(op.get_bind(), checkfirst=True)
    provisioning_sync_status.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "provisioning_sync_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entity_type", provisioning_entity_type, nullable=False),
        sa.Column("entity_key", sa.String(length=255), nullable=False),
        sa.Column("operation", provisioning_operation, nullable=False),
        sa.Column("superset_id", sa.Integer(), nullable=True),
        sa.Column("status", provisioning_sync_status, nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_provisioning_sync_log_tenant_id",
        "provisioning_sync_log",
        ["tenant_id"],
    )
    op.create_index(
        "ix_provisioning_sync_log_entity_key",
        "provisioning_sync_log",
        ["entity_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_provisioning_sync_log_entity_key", table_name="provisioning_sync_log")
    op.drop_index("ix_provisioning_sync_log_tenant_id", table_name="provisioning_sync_log")
    op.drop_table("provisioning_sync_log")
    provisioning_sync_status.drop(op.get_bind(), checkfirst=True)
    provisioning_operation.drop(op.get_bind(), checkfirst=True)
    provisioning_entity_type.drop(op.get_bind(), checkfirst=True)
