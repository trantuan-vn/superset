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
"""JSON serialization helpers for SSO attributes."""

import json

from app.auth.serialize import json_safe_attributes


def test_json_safe_attributes_strips_password_and_bytes() -> None:
    raw = {
        "uid": [b"cntt.cv"],
        "mail": ["cntt.cv@demo-corp.local"],
        "userPassword": [b"Pass123!"],
    }
    safe = json_safe_attributes(raw)
    json.dumps(safe)
    assert "userPassword" not in safe
    assert safe["uid"] == ["cntt.cv"]
