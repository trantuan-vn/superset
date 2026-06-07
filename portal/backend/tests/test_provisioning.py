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
"""Provisioning service tests — Phase 5."""

import uuid
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.auth.dependencies import require_tenant_admin
from app.config import Settings
from app.main import app
from app.models.department import DeptRole
from app.models.provisioning_sync_log import ProvisioningSyncStatus
from app.models.user import SystemRole, User, UserStatus
from app.provisioning.blueprint import (
    active_role_name,
    blueprint_for_role_name,
    cntt_cv_role_name,
    dept_cv_role_name,
    dept_ld_role_name,
    inactive_role_name,
    is_export_permission,
    superset_role_names_for_user,
    superset_username,
)
from app.provisioning.blueprint import RoleBlueprint
from app.provisioning.rison import encode_rison
from app.provisioning.service import ProvisioningService
from app.provisioning.superset_client import SupersetClientError, SupersetRole, SupersetUser
from app.seed import DEMO_TENANT_ID

client = TestClient(app)


def test_role_naming_convention() -> None:
    assert cntt_cv_role_name("demo-corp") == "t_demo-corp_cntt_cv"
    assert dept_cv_role_name("demo-corp", "KETOAN") == "t_demo-corp_d_KETOAN_cv"
    assert dept_ld_role_name("demo-corp", "KETOAN") == "t_demo-corp_d_KETOAN_ld"


def test_inactive_role_name_roundtrip() -> None:
    active = dept_cv_role_name("demo-corp", "KETOAN")
    inactive = inactive_role_name(active)
    assert inactive == "t_demo-corp_d_KETOAN_cv__inactive"
    assert active_role_name(inactive) == active
    assert blueprint_for_role_name(inactive) == RoleBlueprint.DEPT_CV


def test_superset_username_scoped_to_tenant() -> None:
    assert superset_username("demo-corp", "cntt.cv@demo-corp") == (
        "t_demo-corp__cntt.cv@demo-corp"
    )


def test_superset_role_mapping_cntt_cv() -> None:
    roles = superset_role_names_for_user("demo-corp", SystemRole.CNTT_CHUYENVIEN)
    assert roles == ["t_demo-corp_cntt_cv"]


def test_superset_role_mapping_dept_ld() -> None:
    roles = superset_role_names_for_user(
        "demo-corp",
        SystemRole.DEPT_USER,
        dept_code="KETOAN",
        dept_role=DeptRole.LANHDAO,
    )
    assert roles == ["t_demo-corp_d_KETOAN_ld"]


def test_export_permissions_filtered() -> None:
    assert is_export_permission("can_export")
    assert is_export_permission("can_csv")
    assert not is_export_permission("can_read")


def test_rison_encode_role_filter() -> None:
    encoded = encode_rison(
        {
            "filters": [{"col": "name", "opr": "eq", "value": "t_demo-corp_cntt_cv"}],
            "page": 0,
            "page_size": 1,
        }
    )
    assert "t_demo-corp_cntt_cv" in encoded
    assert "filters" in encoded


def test_provision_role_skipped_when_disabled() -> None:
    db = MagicMock()
    settings = Settings(superset_service_api_key="")
    service = ProvisioningService(db, settings=settings)

    result = service.provision_department_roles("demo-corp", DEMO_TENANT_ID, "KETOAN")

    assert len(result) == 2
    assert all(r.status == ProvisioningSyncStatus.SKIPPED for r in result)


def test_ensure_active_role_restores_inactive_suffix() -> None:
    db = MagicMock()
    settings = Settings(superset_service_api_key="sst_test_key")
    mock_client = MagicMock()
    mock_client.enabled = True
    active_name = dept_cv_role_name("demo-corp", "KETOAN")
    inactive_name = inactive_role_name(active_name)

    def find_role(name: str) -> SupersetRole | None:
        if name == active_name:
            return None
        if name == inactive_name:
            return SupersetRole(id=8, name=inactive_name, permission_ids=(), user_ids=())
        if name == active_name:
            return SupersetRole(id=8, name=active_name, permission_ids=(), user_ids=())
        return None

    restored = SupersetRole(id=8, name=active_name, permission_ids=(), user_ids=())

    call_count = {"n": 0}

    def find_after_rename(name: str) -> SupersetRole | None:
        call_count["n"] += 1
        if name == active_name and call_count["n"] > 1:
            return restored
        return find_role(name)

    mock_client.find_role_by_name.side_effect = find_after_rename

    service = ProvisioningService(db, client=mock_client, settings=settings)
    role = service._ensure_active_role(active_name)

    assert role is not None
    assert role.name == active_name
    mock_client.update_role_name.assert_called_once_with(8, active_name)


def test_provision_role_success_with_mock_client() -> None:
    db = MagicMock()
    settings = Settings(superset_service_api_key="sst_test_key")
    mock_client = MagicMock()
    mock_client.enabled = True
    mock_client.find_role_by_name.return_value = None
    mock_client.create_role.return_value = SupersetRole(
        id=42,
        name="t_demo-corp_d_KETOAN_cv",
        permission_ids=(),
        user_ids=(),
    )
    mock_client.list_permissions_page.return_value = ([], 0)

    service = ProvisioningService(db, client=mock_client, settings=settings)
    service._get_or_create_log = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock(
            entity_key="t_demo-corp_d_KETOAN_cv",
            attempts=0,
            tenant_id=DEMO_TENANT_ID,
        )
    )
    service._mark_success = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda log, sid, **kwargs: __import__(
            "app.provisioning.service", fromlist=["ProvisioningResult"]
        ).ProvisioningResult(
            entity_key=log.entity_key,
            status=ProvisioningSyncStatus.SUCCESS,
            superset_id=sid,
        )
    )

    result = service._provision_role(
        tenant_id=DEMO_TENANT_ID,
        role_name="t_demo-corp_d_KETOAN_cv",
        blueprint=__import__(
            "app.provisioning.blueprint", fromlist=["RoleBlueprint"]
        ).RoleBlueprint.DEPT_CV,
        operation=__import__(
            "app.models.provisioning_sync_log", fromlist=["ProvisioningOperation"]
        ).ProvisioningOperation.CREATE,
    )

    assert result.status == ProvisioningSyncStatus.SUCCESS
    assert result.superset_id == 42
    mock_client.create_role.assert_called_once()


def test_provision_role_failure_schedules_retry() -> None:
    db = MagicMock()
    settings = Settings(
        superset_service_api_key="sst_test_key",
        provisioning_max_retries=3,
    )
    mock_client = MagicMock()
    mock_client.enabled = True
    mock_client.find_role_by_name.side_effect = SupersetClientError("connection refused")

    log = MagicMock()
    log.entity_key = "t_demo-corp_cntt_cv"
    log.attempts = 0
    log.tenant_id = DEMO_TENANT_ID

    service = ProvisioningService(db, client=mock_client, settings=settings)
    service._get_or_create_log = MagicMock(return_value=log)  # type: ignore[method-assign]

    with patch.object(service, "_mark_failure") as mark_failure:
        mark_failure.return_value = __import__(
            "app.provisioning.service", fromlist=["ProvisioningResult"]
        ).ProvisioningResult(
            entity_key=log.entity_key,
            status=ProvisioningSyncStatus.FAILED,
            message="connection refused",
        )
        result = service._provision_role(
            tenant_id=DEMO_TENANT_ID,
            role_name="t_demo-corp_cntt_cv",
            blueprint=__import__(
                "app.provisioning.blueprint", fromlist=["RoleBlueprint"]
            ).RoleBlueprint.CNTT_CV,
            operation=__import__(
                "app.models.provisioning_sync_log", fromlist=["ProvisioningOperation"]
            ).ProvisioningOperation.CREATE,
        )

    assert result.status == ProvisioningSyncStatus.FAILED
    mark_failure.assert_called_once()


def _tenant_admin() -> User:
    return User(
        id=uuid.uuid4(),
        tenant_id=DEMO_TENANT_ID,
        username="admin@demo-corp",
        email="admin@demo-corp",
        display_name="Admin",
        password_hash="x",
        system_role=SystemRole.TENANT_ADMIN,
        status=UserStatus.ACTIVE,
    )


def test_provisioning_status_requires_auth() -> None:
    response = client.get("/provisioning/status")
    assert response.status_code == 401


def test_provisioning_status_as_tenant_admin() -> None:
    admin = _tenant_admin()
    app.dependency_overrides[require_tenant_admin] = lambda: admin
    try:
        with patch(
            "app.api.provisioning.ProvisioningService.get_latest_status",
            return_value=[],
        ), patch(
            "app.api.provisioning.SupersetClient.health_check",
            return_value=False,
        ), patch(
            "app.api.provisioning.ProvisioningService.enabled",
            new_callable=lambda: property(lambda self: False),
        ):
            response = client.get("/provisioning/status")
        assert response.status_code == 200
        body = response.json()
        assert body["enabled"] is False
        assert body["logs"] == []
    finally:
        app.dependency_overrides.clear()
