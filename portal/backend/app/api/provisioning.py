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
"""Provisioning status API — Phase 5."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.schemas import (
    MessageResponse,
    ProvisioningLogResponse,
    ProvisioningStatusResponse,
)
from app.auth.dependencies import require_tenant_admin
from app.db import get_db
from app.models.user import User
from app.provisioning.service import ProvisioningService
from app.provisioning.superset_client import SupersetClient

router = APIRouter(prefix="/provisioning", tags=["provisioning"])


def _log_to_response(log: object) -> ProvisioningLogResponse:
    from app.models.provisioning_sync_log import ProvisioningSyncLog

    entry = log
    assert isinstance(entry, ProvisioningSyncLog)
    return ProvisioningLogResponse(
        id=str(entry.id),
        entity_type=entry.entity_type.value,
        entity_key=entry.entity_key,
        operation=entry.operation.value,
        superset_id=entry.superset_id,
        status=entry.status.value,
        error_message=entry.error_message,
        attempts=entry.attempts,
        updated_at=entry.updated_at.isoformat(),
    )


@router.get("/status", response_model=ProvisioningStatusResponse)
def provisioning_status(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin)],
    entity_key: Annotated[str | None, Query()] = None,
) -> ProvisioningStatusResponse:
    """Return latest provisioning sync entries for the tenant."""
    service = ProvisioningService(db)
    logs = service.get_latest_status(user.tenant_id, entity_key=entity_key)
    client = SupersetClient()
    return ProvisioningStatusResponse(
        enabled=service.enabled,
        superset_reachable=client.health_check() if service.enabled else False,
        logs=[_log_to_response(entry) for entry in logs],
    )


@router.post("/retry", response_model=MessageResponse)
def retry_provisioning(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_tenant_admin)],
) -> MessageResponse:
    """Retry failed provisioning jobs for the current tenant."""
    service = ProvisioningService(db)
    count = service.process_pending_retries()
    return MessageResponse(message=f"Retried {count} provisioning job(s)")
