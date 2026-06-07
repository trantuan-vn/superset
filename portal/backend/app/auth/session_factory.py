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
"""Session creation with optional PKI gate."""

import uuid

from app.auth.pki_policy import pki_required_for_tenant
from app.auth.session import create_session
from app.config import get_settings
from app.models.tenant import TenantSettings


def create_auth_session(
    user_id: uuid.UUID,
    tenant_id: uuid.UUID,
    settings: TenantSettings,
) -> tuple[str, int, bool]:
    """Create session; returns (session_id, ttl, pki_pending)."""
    app_settings = get_settings()
    pki_required = pki_required_for_tenant(settings)
    if pki_required:
        ttl_seconds = app_settings.pki_pending_session_minutes * 60
    else:
        ttl_seconds = app_settings.session_ttl_hours * 3600
    session_id, ttl = create_session(
        user_id,
        tenant_id,
        pki_required=pki_required,
        pki_verified=False,
        ttl_seconds=ttl_seconds,
    )
    return session_id, ttl, pki_required
