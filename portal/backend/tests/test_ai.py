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
"""AI orchestrator tests — Phase 7."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.ai.sql_validator import validate_read_only_sql
from app.auth.dependencies import require_cntt_chuyenvien
from app.main import app
from app.models.tenant import Tenant, TenantSettings
from app.models.user import SystemRole, User, UserStatus
from app.seed import DEMO_TENANT_ID

client = TestClient(app)


def _cntt_cv() -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username="cntt.cv@demo-corp",
        email="cntt.cv@demo-corp",
        display_name="CNTT CV",
        password_hash="x",
        system_role=SystemRole.CNTT_CHUYENVIEN,
        status=UserStatus.ACTIVE,
    )


def _cntt_ld() -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username="cntt.ld@demo-corp",
        email="cntt.ld@demo-corp",
        display_name="CNTT LD",
        password_hash="x",
        system_role=SystemRole.CNTT_LANHDAO,
        status=UserStatus.ACTIVE,
    )


def test_sql_validator_allows_select() -> None:
    result = validate_read_only_sql(
        "SELECT id FROM portal_export_data WHERE tenant_id = 'x' LIMIT 10"
    )
    assert result.valid is True


def test_sql_validator_blocks_delete() -> None:
    result = validate_read_only_sql("DELETE FROM portal_export_data")
    assert result.valid is False
    assert result.reason is not None
    assert "delete" in result.reason.lower()


def test_sql_validator_blocks_multiple_statements() -> None:
    result = validate_read_only_sql("SELECT 1; DROP TABLE users")
    assert result.valid is False


def test_require_cntt_chuyenvien_blocks_lanhdao() -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        require_cntt_chuyenvien(_cntt_ld())
    assert exc_info.value.status_code == 403


def test_generate_sql_blocked_when_ai_disabled() -> None:
    cv = _cntt_cv()
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-corp",
        name="Demo Corp",
        status="active",
    )
    settings = TenantSettings(
        tenant_id=DEMO_TENANT_ID,
        ai_enabled=False,
    )

    app.dependency_overrides[require_cntt_chuyenvien] = lambda: cv
    try:
        with (
            patch("app.api.ai._tenant_for_user", return_value=tenant),
            patch(
                "app.api.ai.generate_sql_draft",
                new_callable=AsyncMock,
                side_effect=__import__(
                    "app.ai.service", fromlist=["AiServiceError"]
                ).AiServiceError("AI is disabled for this tenant. Enter SQL manually.", status_code=403),
            ),
        ):
            response = client.post(
                "/ai/generate-sql",
                json={"prompt": "show sales"},
            )
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_generate_sql_success() -> None:
    cv = _cntt_cv()
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-corp",
        name="Demo Corp",
        status="active",
    )
    settings = TenantSettings(
        tenant_id=DEMO_TENANT_ID,
        ai_enabled=True,
        ai_config={"provider": "mock"},
    )

    from app.ai.service import GenerateSqlResult, generate_sql_draft

    db = MagicMock()
    with (
        patch("app.ai.service.get_tenant_settings", return_value=settings),
        patch("app.ai.service.check_ai_rate_limit", return_value=1),
        patch("app.ai.service.write_audit_log"),
    ):
        result = await generate_sql_draft(
            db,
            user=cv,
            tenant=tenant,
            prompt="show all export rows",
        )
    assert isinstance(result, GenerateSqlResult)
    assert result.blocked is False
    assert "SELECT" in result.sql.upper()


@pytest.mark.asyncio
async def test_generate_sql_blocks_dangerous_output() -> None:
    cv = _cntt_cv()
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-corp",
        name="Demo Corp",
        status="active",
    )
    settings = TenantSettings(
        tenant_id=DEMO_TENANT_ID,
        ai_enabled=True,
        ai_config={"provider": "mock"},
    )

    from app.ai.adapters.mock import MockLlmAdapter
    from app.ai.service import generate_sql_draft

    class EvilAdapter(MockLlmAdapter):
        async def generate_sql(self, request):  # type: ignore[no-untyped-def]
            return "DROP TABLE portal_export_data"

    db = MagicMock()
    with (
        patch("app.ai.service.get_tenant_settings", return_value=settings),
        patch("app.ai.service.check_ai_rate_limit", return_value=1),
        patch("app.ai.service.get_llm_adapter", return_value=EvilAdapter()),
        patch("app.ai.service.write_audit_log"),
    ):
        result = await generate_sql_draft(
            db,
            user=cv,
            tenant=tenant,
            prompt="drop everything",
        )
    assert result.blocked is True
    assert result.block_reason is not None


def test_mcp_token_mints_jwt() -> None:
    cv = _cntt_cv()
    tenant = Tenant(
        id=DEMO_TENANT_ID,
        slug="demo-corp",
        name="Demo Corp",
        status="active",
    )
    settings = TenantSettings(
        tenant_id=DEMO_TENANT_ID,
        ai_enabled=True,
    )

    app.dependency_overrides[require_cntt_chuyenvien] = lambda: cv
    try:
        with (
            patch("app.api.ai._tenant_for_user", return_value=tenant),
            patch("app.api.ai.issue_mcp_token") as mock_issue,
        ):
            from app.ai.service import McpTokenResult

            mock_issue.return_value = McpTokenResult(
                token="jwt-token",
                expires_in_seconds=900,
                superset_username="t_demo-corp__cntt.cv@demo-corp",
            )
            response = client.get("/ai/mcp-token")
        assert response.status_code == 200
        body = response.json()
        assert body["token"] == "jwt-token"
        assert body["expires_in_seconds"] == 900
    finally:
        app.dependency_overrides.clear()
