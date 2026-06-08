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
"""Add request_reason to export_transactions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0012_export_transaction_reason"
down_revision: str | None = "0011_export_transactions"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "export_transactions",
        sa.Column("request_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("export_transactions", "request_reason")
