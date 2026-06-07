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
"""Departments and user_dept_roles tables — Phase 4.

Revision ID: 0006_departments
Revises: 0005_platform_admin
Create Date: 2026-06-07
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006_departments"
down_revision: Union[str, None] = "0005_platform_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

department_status = postgresql.ENUM(
    "active",
    "inactive",
    name="department_status",
    create_type=False,
)
dept_role = postgresql.ENUM(
    "chuyenvien",
    "lanhdao",
    name="dept_role",
    create_type=False,
)


def upgrade() -> None:
    department_status.create(op.get_bind(), checkfirst=True)
    dept_role.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "departments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column(
            "status",
            department_status,
            nullable=False,
            server_default="active",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_departments_tenant_code"),
    )
    op.create_index("ix_departments_tenant_id", "departments", ["tenant_id"])

    op.create_table(
        "user_dept_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("department_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", dept_role, nullable=False),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "department_id", name="uq_user_dept_roles_user_dept"
        ),
    )
    op.create_index("ix_user_dept_roles_user_id", "user_dept_roles", ["user_id"])
    op.create_index(
        "ix_user_dept_roles_department_id", "user_dept_roles", ["department_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_user_dept_roles_department_id", table_name="user_dept_roles")
    op.drop_index("ix_user_dept_roles_user_id", table_name="user_dept_roles")
    op.drop_table("user_dept_roles")
    op.drop_index("ix_departments_tenant_id", table_name="departments")
    op.drop_table("departments")
    dept_role.drop(op.get_bind(), checkfirst=True)
    department_status.drop(op.get_bind(), checkfirst=True)
