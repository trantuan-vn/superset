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
"""AI orchestrator API — Phase 7."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.service import AiServiceError, generate_sql_draft, issue_mcp_token, stream_sql_draft
from app.api.schemas import (
    GenerateSqlRequest,
    GenerateSqlResponse,
    McpTokenResponse,
)
from app.auth.dependencies import require_cntt_chuyenvien
from app.db import get_db
from app.models.tenant import Tenant
from app.models.user import User

router = APIRouter(prefix="/ai", tags=["ai"])


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


def _tenant_for_user(db: Session, user: User) -> Tenant:
    tenant = db.scalar(select(Tenant).where(Tenant.id == user.tenant_id))
    if tenant is None:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return tenant


@router.post("/generate-sql", response_model=GenerateSqlResponse)
async def generate_sql(
    body: GenerateSqlRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_cntt_chuyenvien)],
) -> GenerateSqlResponse:
    tenant = _tenant_for_user(db, user)
    try:
        result = await generate_sql_draft(
            db,
            user=user,
            tenant=tenant,
            prompt=body.prompt,
            context_sql=body.context_sql,
            dataset_hint=body.dataset_hint,
            ip_address=_client_ip(request),
        )
    except AiServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if result.blocked:
        raise HTTPException(
            status_code=422,
            detail=result.block_reason or "Generated SQL was blocked",
        )
    return GenerateSqlResponse(sql=result.sql)


@router.post("/generate-sql/stream")
async def generate_sql_stream(
    body: GenerateSqlRequest,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_cntt_chuyenvien)],
) -> StreamingResponse:
    tenant = _tenant_for_user(db, user)

    async def event_stream():
        try:
            async for chunk in stream_sql_draft(
                db,
                user=user,
                tenant=tenant,
                prompt=body.prompt,
                context_sql=body.context_sql,
                dataset_hint=body.dataset_hint,
                ip_address=_client_ip(request),
            ):
                payload = json.dumps({"type": "chunk", "content": chunk})
                yield f"data: {payload}\n\n"
            yield f"data: {json.dumps({'type': 'done'})}\n\n"
        except AiServiceError as exc:
            payload = json.dumps({"type": "error", "message": exc.message})
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get("/mcp-token", response_model=McpTokenResponse)
def get_mcp_token(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_cntt_chuyenvien)],
) -> McpTokenResponse:
    tenant = _tenant_for_user(db, user)
    try:
        result = issue_mcp_token(
            db,
            user=user,
            tenant=tenant,
            ip_address=_client_ip(request),
        )
    except AiServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return McpTokenResponse(
        token=result.token,
        expires_in_seconds=result.expires_in_seconds,
        superset_username=result.superset_username,
    )
