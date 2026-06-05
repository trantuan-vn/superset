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
"""user_auth_identities table — Phase 2 SSO/LDAP.

Revision ID: 0003_user_auth_identities
Revises: 0002_users_audit
Create Date: 2026-06-05
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_user_auth_identities"
down_revision: Union[str, None] = "0002_users_audit"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

auth_provider = postgresql.ENUM(
    "local",
    "oidc",
    "saml",
    "ldap",
    name="auth_provider",
    create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    auth_provider.create(bind, checkfirst=True)

    inspector = sa.inspect(bind)
    if "user_auth_identities" in inspector.get_table_names():
        return

    op.create_table(
        "user_auth_identities",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", auth_provider, nullable=False),
        sa.Column("external_id", sa.String(length=255), nullable=False),
        sa.Column("raw_attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "provider",
            name="uq_user_auth_identities_user_provider",
        ),
    )
    op.create_index(
        "ix_user_auth_identities_user_id",
        "user_auth_identities",
        ["user_id"],
    )
    op.create_index(
        "ix_user_auth_identities_provider_external",
        "user_auth_identities",
        ["provider", "external_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_user_auth_identities_provider_external",
        table_name="user_auth_identities",
    )
    op.drop_index("ix_user_auth_identities_user_id", table_name="user_auth_identities")
    op.drop_table("user_auth_identities")
    auth_provider.drop(op.get_bind(), checkfirst=True)
