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
"""AI orchestration — SQL generation and MCP token minting."""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.ai.adapters import SqlGenerationRequest, get_llm_adapter
from app.ai.mcp_jwt import mint_mcp_jwt
from app.ai.rate_limit import AiRateLimitExceeded, check_ai_rate_limit
from app.ai.sql_validator import validate_read_only_sql
from app.audit.service import write_audit_log
from app.models.tenant import Tenant, TenantSettings
from app.models.user import User
from app.tenants.service import get_tenant_settings


class AiServiceError(Exception):
    """Domain error for AI operations."""

    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class GenerateSqlResult:
    sql: str
    blocked: bool
    block_reason: str | None = None


@dataclass(frozen=True)
class McpTokenResult:
    token: str
    expires_in_seconds: int
    superset_username: str


def _require_ai_enabled(settings: TenantSettings) -> None:
    if not settings.ai_enabled:
        raise AiServiceError(
            "AI is disabled for this tenant. Enter SQL manually.",
            status_code=403,
        )


def _validate_generated_sql(sql: str) -> GenerateSqlResult:
    validation = validate_read_only_sql(sql)
    if not validation.valid:
        return GenerateSqlResult(
            sql=sql,
            blocked=True,
            block_reason=validation.reason,
        )
    return GenerateSqlResult(sql=sql, blocked=False)


async def generate_sql_draft(
    db: Session,
    *,
    user: User,
    tenant: Tenant,
    prompt: str,
    context_sql: str | None = None,
    dataset_hint: str | None = None,
    ip_address: str | None = None,
) -> GenerateSqlResult:
    """Generate SQL via tenant-configured LLM adapter."""
    settings = get_tenant_settings(db, tenant.id)
    _require_ai_enabled(settings)

    try:
        check_ai_rate_limit(tenant_id=tenant.id, user_id=user.id)
    except AiRateLimitExceeded as exc:
        raise AiServiceError(str(exc), status_code=429) from exc

    adapter = get_llm_adapter(settings.ai_config)
    request = SqlGenerationRequest(
        prompt=prompt,
        context_sql=context_sql,
        dataset_hint=dataset_hint,
    )
    try:
        raw_sql = await adapter.generate_sql(request)
    except Exception as exc:
        raise AiServiceError(
            f"AI provider error: {exc}",
            status_code=502,
        ) from exc

    result = _validate_generated_sql(raw_sql)
    write_audit_log(
        db,
        tenant_id=tenant.id,
        action="AI_GENERATE_SQL",
        entity_type="ai",
        entity_id=str(user.id),
        actor_id=user.id,
        payload={
            "prompt_length": len(prompt.strip()),
            "blocked": result.blocked,
            "block_reason": result.block_reason,
            "has_context_sql": bool(context_sql and context_sql.strip()),
        },
        ip_address=ip_address,
    )
    return result


async def stream_sql_draft(
    db: Session,
    *,
    user: User,
    tenant: Tenant,
    prompt: str,
    context_sql: str | None = None,
    dataset_hint: str | None = None,
    ip_address: str | None = None,
) -> AsyncIterator[str]:
    """Stream SQL chunks; validates the assembled SQL after completion."""
    settings = get_tenant_settings(db, tenant.id)
    _require_ai_enabled(settings)

    try:
        check_ai_rate_limit(tenant_id=tenant.id, user_id=user.id)
    except AiRateLimitExceeded as exc:
        raise AiServiceError(str(exc), status_code=429) from exc

    adapter = get_llm_adapter(settings.ai_config)
    request = SqlGenerationRequest(
        prompt=prompt,
        context_sql=context_sql,
        dataset_hint=dataset_hint,
    )

    buffer = ""
    try:
        async for chunk in adapter.stream_sql(request):
            buffer += chunk
            yield chunk
    except Exception as exc:
        raise AiServiceError(
            f"AI provider error: {exc}",
            status_code=502,
        ) from exc

    result = _validate_generated_sql(buffer)
    write_audit_log(
        db,
        tenant_id=tenant.id,
        action="AI_GENERATE_SQL",
        entity_type="ai",
        entity_id=str(user.id),
        actor_id=user.id,
        payload={
            "prompt_length": len(prompt.strip()),
            "blocked": result.blocked,
            "block_reason": result.block_reason,
            "streamed": True,
            "has_context_sql": bool(context_sql and context_sql.strip()),
        },
        ip_address=ip_address,
    )
    if result.blocked:
        raise AiServiceError(
            result.block_reason or "Generated SQL was blocked",
            status_code=422,
        )


def issue_mcp_token(
    db: Session,
    *,
    user: User,
    tenant: Tenant,
    ip_address: str | None = None,
) -> McpTokenResult:
    """Mint a short-lived MCP JWT for the authenticated cntt_chuyenvien."""
    settings = get_tenant_settings(db, tenant.id)
    _require_ai_enabled(settings)

    try:
        token, expires_in = mint_mcp_jwt(user=user, tenant=tenant)
    except ValueError as exc:
        raise AiServiceError(str(exc), status_code=503) from exc

    from app.provisioning.blueprint import superset_username as map_username

    superset_user = map_username(tenant.slug, user.username)
    write_audit_log(
        db,
        tenant_id=tenant.id,
        action="AI_MCP_TOKEN_ISSUED",
        entity_type="ai",
        entity_id=str(user.id),
        actor_id=user.id,
        payload={"superset_username": superset_user, "ttl_seconds": expires_in},
        ip_address=ip_address,
    )
    return McpTokenResult(
        token=token,
        expires_in_seconds=expires_in,
        superset_username=superset_user,
    )
