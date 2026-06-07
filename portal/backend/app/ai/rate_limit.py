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
"""Redis-backed rate limiting for AI endpoints."""

import uuid

from app.auth.session import get_redis_client
from app.config import get_settings

AI_RATE_PREFIX = "portal:ai:rate:"


class AiRateLimitExceeded(Exception):
    """Raised when a principal exceeds the configured AI quota."""

    def __init__(self, limit: int, window_seconds: int) -> None:
        super().__init__(f"AI rate limit exceeded ({limit} per {window_seconds}s)")
        self.limit = limit
        self.window_seconds = window_seconds


def _rate_key(tenant_id: uuid.UUID, user_id: uuid.UUID) -> str:
    return f"{AI_RATE_PREFIX}{tenant_id}:{user_id}"


def check_ai_rate_limit(*, tenant_id: uuid.UUID, user_id: uuid.UUID) -> int:
    """
    Increment and enforce per-user AI quota.

    Returns the current count within the window.
    """
    settings = get_settings()
    limit = settings.ai_rate_limit_per_hour
    window = settings.ai_rate_limit_window_seconds
    client = get_redis_client()
    key = _rate_key(tenant_id, user_id)
    count = int(client.incr(key))
    if count == 1:
        client.expire(key, window)
    if count > limit:
        raise AiRateLimitExceeded(limit=limit, window_seconds=window)
    return count
