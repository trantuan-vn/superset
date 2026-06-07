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
"""Add platform_admin system role — multi-tenant operator.

Revision ID: 0005_platform_admin
Revises: 0004_user_certificates
Create Date: 2026-06-05
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0005_platform_admin"
down_revision: Union[str, None] = "0004_user_certificates"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE system_role ADD VALUE IF NOT EXISTS 'platform_admin'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely.
    pass
