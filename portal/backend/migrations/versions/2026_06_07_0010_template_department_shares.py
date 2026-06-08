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
"""Add template_department_shares for SELECTED share mode."""

from typing import Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010_template_department_shares"
down_revision: Union[str, None] = "0009_export_templates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "template_department_shares",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shared_by", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "shared_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["shared_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["template_id"], ["export_templates.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "template_id", "department_id", name="uq_template_department_share"
        ),
    )
    op.create_index(
        "ix_template_department_shares_template_id",
        "template_department_shares",
        ["template_id"],
    )
    op.create_index(
        "ix_template_department_shares_department_id",
        "template_department_shares",
        ["department_id"],
    )
    op.add_column(
        "export_templates",
        sa.Column("superset_dashboard_title", sa.String(length=255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("export_templates", "superset_dashboard_title")
    op.drop_index(
        "ix_template_department_shares_department_id",
        table_name="template_department_shares",
    )
    op.drop_index(
        "ix_template_department_shares_template_id",
        table_name="template_department_shares",
    )
    op.drop_table("template_department_shares")
