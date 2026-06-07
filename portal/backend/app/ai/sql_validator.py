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
"""Read-only SQL validation for AI-generated drafts — Phase 7."""

import re
from dataclasses import dataclass

# Whole-word dangerous keywords (case-insensitive).
_BLOCKED_KEYWORDS = frozenset(
    {
        "delete",
        "drop",
        "truncate",
        "insert",
        "update",
        "alter",
        "create",
        "grant",
        "revoke",
        "merge",
        "replace",
        "call",
        "execute",
        "exec",
        "copy",
        "attach",
        "detach",
        "pragma",
        "vacuum",
        "reindex",
        "shutdown",
        "kill",
    }
)

_BLOCKED_PHRASES = (
    "into outfile",
    "into dumpfile",
    "load data",
    "xp_cmdshell",
    "pg_sleep",
)

_WORD_RE = re.compile(r"[a-z_][a-z0-9_]*", re.IGNORECASE)


@dataclass(frozen=True)
class SqlValidationResult:
    """Outcome of validating a SQL draft."""

    valid: bool
    reason: str | None = None


def _strip_sql_comments(sql: str) -> str:
    """Remove line and block comments for safer keyword scanning."""
    without_block = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    without_line = re.sub(r"--[^\n]*", " ", without_block)
    return without_line


def validate_read_only_sql(sql: str) -> SqlValidationResult:
    """
    Ensure SQL is a single read-only statement (SELECT / WITH … SELECT).

    Gate 7: dangerous statements are rejected before returning to the client.
    """
    trimmed = sql.strip()
    if not trimmed:
        return SqlValidationResult(valid=False, reason="SQL is empty")

    normalized = _strip_sql_comments(trimmed)
    lowered = normalized.lower()

    if ";" in normalized.rstrip(";"):
        return SqlValidationResult(
            valid=False,
            reason="Multiple SQL statements are not allowed",
        )

    for phrase in _BLOCKED_PHRASES:
        if phrase in lowered:
            return SqlValidationResult(
                valid=False,
                reason=f"Blocked SQL pattern: {phrase}",
            )

    words = {match.group(0).lower() for match in _WORD_RE.finditer(normalized)}
    blocked = sorted(words & _BLOCKED_KEYWORDS)
    if blocked:
        return SqlValidationResult(
            valid=False,
            reason=f"Blocked keyword(s): {', '.join(blocked)}",
        )

    stripped = lowered.lstrip()
    if not (stripped.startswith("select") or stripped.startswith("with")):
        return SqlValidationResult(
            valid=False,
            reason="Only SELECT queries are allowed",
        )

    return SqlValidationResult(valid=True)
