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
"""SQL preview helper — Phase 8."""

from __future__ import annotations

import re
from typing import Any

from app.ai.sql_validator import validate_read_only_sql

_PREVIEW_LIMIT = 100
_SELECT_LIST_RE = re.compile(
    r"^\s*(?:with\b[\s\S]+?\)\s*)?select\s+(distinct\s+)?(.+?)\s+from\b",
    re.IGNORECASE | re.DOTALL,
)


def _extract_columns(sql: str) -> list[str]:
    match = _SELECT_LIST_RE.search(sql)
    if not match:
        return ["col1", "col2", "col3"]
    select_list = match.group(2) or ""
    if select_list.strip() == "*":
        return ["tenant_id", "department_code", "amount", "created_at"]
    columns: list[str] = []
    for part in select_list.split(","):
        token = part.strip()
        if not token:
            continue
        alias_match = re.search(r"\bas\s+([a-z_][a-z0-9_]*)", token, re.IGNORECASE)
        if alias_match:
            columns.append(alias_match.group(1))
            continue
        bare = token.split(".")[-1].strip()
        bare = bare.strip('"').strip("'").strip("`")
        if bare:
            columns.append(bare)
    return columns or ["col1"]


def preview_sql(sql: str) -> dict[str, Any]:
    """Return up to 100 preview rows after validating read-only SQL."""
    validation = validate_read_only_sql(sql)
    if not validation.valid:
        raise ValueError(validation.reason or "Invalid SQL")

    columns = _extract_columns(sql)
    rows: list[dict[str, Any]] = []
    for index in range(min(5, _PREVIEW_LIMIT)):
        row = {column: f"sample_{index + 1}" for column in columns}
        rows.append(row)

    return {
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": False,
        "mock": True,
    }
