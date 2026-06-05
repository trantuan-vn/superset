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
"""JSON-safe serialization for IdP attribute snapshots."""

from typing import Any

_SENSITIVE_ATTRS = frozenset({"userPassword", "userpassword", "unicodePwd"})


def json_safe(value: Any) -> Any:
    """Convert LDAP/OIDC attribute values to JSON-serializable types."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {
            str(key): json_safe(item)
            for key, item in value.items()
            if str(key) not in _SENSITIVE_ATTRS
        }
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return str(value)


def json_safe_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    """Sanitize a flat attribute map for JSONB storage."""
    safe = json_safe(attributes)
    if isinstance(safe, dict):
        return safe
    return {}
