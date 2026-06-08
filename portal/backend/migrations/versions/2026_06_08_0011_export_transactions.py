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
"""Add export_transactions for dept export workflow."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_export_transactions"
down_revision: str | None = "0010_template_department_shares"
branch_labels: str | None = None
depends_on: str | None = None

export_transaction_status = postgresql.ENUM(
    "draft",
    "submitted",
    "approved",
    "rejected",
    "downloaded",
    name="export_transaction_status",
    create_type=False,
)


def upgrade() -> None:
    export_transaction_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "export_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("params_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", export_transaction_status, nullable=False),
        sa.Column("reject_comment", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["template_id"], ["export_templates.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_export_transactions_tenant_id",
        "export_transactions",
        ["tenant_id"],
    )
    op.create_index(
        "ix_export_transactions_template_id",
        "export_transactions",
        ["template_id"],
    )
    op.create_index(
        "ix_export_transactions_department_id",
        "export_transactions",
        ["department_id"],
    )
    op.create_index(
        "ix_export_transactions_status",
        "export_transactions",
        ["status"],
    )
    op.create_index(
        "ix_export_transactions_created_by",
        "export_transactions",
        ["created_by"],
    )


def downgrade() -> None:
    op.drop_index("ix_export_transactions_created_by", table_name="export_transactions")
    op.drop_index("ix_export_transactions_status", table_name="export_transactions")
    op.drop_index("ix_export_transactions_department_id", table_name="export_transactions")
    op.drop_index("ix_export_transactions_template_id", table_name="export_transactions")
    op.drop_index("ix_export_transactions_tenant_id", table_name="export_transactions")
    op.drop_table("export_transactions")
    export_transaction_status.drop(op.get_bind(), checkfirst=True)
