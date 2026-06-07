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
"""Export template workflow tests — Phase 8."""

import uuid
from unittest.mock import patch

from fastapi.testclient import TestClient

from datetime import datetime, timezone

from app.auth.dependencies import get_current_user_with_dept_roles, get_session_data
from app.auth.session import SessionData
from app.main import app
from app.models.export_template import ExportTemplate, TemplateStatus
from app.models.tenant import TenantSettings
from app.models.user import SystemRole, User, UserStatus
from app.seed import DEMO_TENANT_ID
from app.templates.service import TemplateError

client = TestClient(app)

SAMPLE_SQL = (
    "SELECT tenant_id, department_code\n"
    "FROM portal_export_data\n"
    "WHERE tenant_id = 'demo'\n"
    "LIMIT 100"
)


def _user(role: SystemRole, *, user_id: uuid.UUID | None = None) -> User:
    return User(
        id=user_id or uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username=f"{role.value}@demo-corp",
        email=f"{role.value}@demo-corp",
        display_name=role.value,
        password_hash="x",
        system_role=role,
        status=UserStatus.ACTIVE,
    )


def _template(
    *,
    creator: User,
    status: TemplateStatus = TemplateStatus.DRAFT,
) -> ExportTemplate:
    now = datetime.now(timezone.utc)
    return ExportTemplate(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        name="Demo template",
        description="Test",
        sql_snapshot=SAMPLE_SQL,
        status=status,
        created_by=creator.id,
        share_scope_version=0,
        created_at=now,
        updated_at=now,
    )


def _session() -> SessionData:
    return SessionData(
        session_id="test-session",
        user_id=str(uuid.uuid4()),
        tenant_id=str(DEMO_TENANT_ID),
        created_at="2026-06-07T00:00:00Z",
        expires_at="2026-06-08T00:00:00Z",
        pki_required=False,
        pki_verified=True,
    )


def test_list_templates_requires_auth() -> None:
    response = client.get("/templates")
    assert response.status_code == 401


def test_create_template_as_cv() -> None:
    cv = _user(SystemRole.CNTT_CHUYENVIEN)
    app.dependency_overrides[get_current_user_with_dept_roles] = lambda: cv
    try:
        with patch(
            "app.api.templates.create_template",
            return_value=_template(creator=cv),
        ):
            response = client.post(
                "/templates",
                json={"name": "Demo template", "sql_snapshot": SAMPLE_SQL},
            )
        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Demo template"
        assert body["status"] == "draft"
    finally:
        app.dependency_overrides.clear()


def test_submit_template_transitions_to_review() -> None:
    cv = _user(SystemRole.CNTT_CHUYENVIEN)
    db_template = _template(creator=cv)
    db_template.status = TemplateStatus.REVIEW
    app.dependency_overrides[get_current_user_with_dept_roles] = lambda: cv
    try:
        with patch(
            "app.api.templates.submit_template",
            return_value=db_template,
        ):
            response = client.post(f"/templates/{db_template.id}/submit")
        assert response.status_code == 200
        assert response.json()["status"] == "review"
    finally:
        app.dependency_overrides.clear()


def test_reject_requires_comment() -> None:
    ld = _user(SystemRole.CNTT_LANHDAO)
    db_template = _template(creator=_user(SystemRole.CNTT_CHUYENVIEN), status=TemplateStatus.REVIEW)
    app.dependency_overrides[get_current_user_with_dept_roles] = lambda: ld
    try:
        with patch(
            "app.api.templates.reject_template",
            side_effect=TemplateError("Reject comment is required", status_code=422),
        ):
            response = client.post(
                f"/templates/{db_template.id}/reject",
                json={"comment": "   "},
            )
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_reject_returns_to_draft_with_comment() -> None:
    cv = _user(SystemRole.CNTT_CHUYENVIEN)
    ld = _user(SystemRole.CNTT_LANHDAO)
    db_template = _template(creator=cv, status=TemplateStatus.DRAFT)
    db_template.reject_comment = "SQL thiếu filter phòng ban"
    app.dependency_overrides[get_current_user_with_dept_roles] = lambda: ld
    try:
        with patch(
            "app.api.templates.reject_template",
            return_value=db_template,
        ):
            response = client.post(
                f"/templates/{db_template.id}/reject",
                json={"comment": "SQL thiếu filter phòng ban"},
            )
        assert response.status_code == 200
        assert response.json()["status"] == "draft"
        assert response.json()["reject_comment"] == "SQL thiếu filter phòng ban"
    finally:
        app.dependency_overrides.clear()


def test_approve_published() -> None:
    ld = _user(SystemRole.CNTT_LANHDAO)
    cv = _user(SystemRole.CNTT_CHUYENVIEN)
    db_template = _template(creator=cv, status=TemplateStatus.PUBLISHED)
    db_template.superset_dashboard_id = 123456
    settings = TenantSettings(tenant_id=DEMO_TENANT_ID)
    app.dependency_overrides[get_current_user_with_dept_roles] = lambda: ld
    app.dependency_overrides[get_session_data] = lambda: _session()
    try:
        with (
            patch("app.api.templates._load_settings", return_value=settings),
            patch(
                "app.api.templates.approve_template",
                return_value=db_template,
            ),
        ):
            response = client.post(f"/templates/{db_template.id}/approve", json={})
        assert response.status_code == 200
        assert response.json()["status"] == "published"
    finally:
        app.dependency_overrides.clear()


def test_preview_validates_sql() -> None:
    cv = _user(SystemRole.CNTT_CHUYENVIEN)
    db_template = _template(creator=cv)
    app.dependency_overrides[get_current_user_with_dept_roles] = lambda: cv
    try:
        with patch(
            "app.api.templates.preview_template_sql",
            return_value={
                "columns": ["tenant_id"],
                "rows": [{"tenant_id": "sample_1"}],
                "row_count": 1,
                "truncated": False,
                "mock": True,
            },
        ):
            response = client.post(
                f"/templates/{db_template.id}/preview",
                json={"sql": SAMPLE_SQL},
            )
        assert response.status_code == 200
        body = response.json()
        assert body["columns"] == ["tenant_id"]
        assert len(body["rows"]) == 1
    finally:
        app.dependency_overrides.clear()


def test_pending_list_requires_approver() -> None:
    cv = _user(SystemRole.CNTT_CHUYENVIEN)
    app.dependency_overrides[get_current_user_with_dept_roles] = lambda: cv
    try:
        with patch(
            "app.api.templates.list_templates",
            side_effect=TemplateError("Template approver access required", status_code=403),
        ):
            response = client.get("/templates?pending=true")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()
