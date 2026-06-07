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
"""Minimal Rison encoder for Superset REST query parameters."""

from typing import Any


def _encode_value(value: Any) -> str:
    if value is None:
        return "!n"
    if isinstance(value, bool):
        return "!t" if value else "!f"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        escaped = value.replace("'", "!'")
        return f"'{escaped}'"
    if isinstance(value, list):
        return f"!({','.join(_encode_value(item) for item in value)})"
    if isinstance(value, dict):
        parts = [f"{key}:{_encode_value(val)}" for key, val in value.items()]
        return f"({','.join(parts)})"
    return f"'{value}'"


def encode_rison(payload: dict[str, Any]) -> str:
    """Encode a dict as a Rison object string for Superset ``?q=`` params."""
    return _encode_value(payload)
