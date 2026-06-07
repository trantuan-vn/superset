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
"""Add RLS entity type to provisioning_sync_log — Phase 6.

Revision ID: 0008_provisioning_rls_entity
Revises: 0007_provisioning_sync_log
Create Date: 2026-06-07
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0008_provisioning_rls_entity"
down_revision: Union[str, None] = "0007_provisioning_sync_log"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TYPE provisioning_entity_type ADD VALUE IF NOT EXISTS 'rls'"
    )


def downgrade() -> None:
    # PostgreSQL does not support removing enum values safely.
    pass
