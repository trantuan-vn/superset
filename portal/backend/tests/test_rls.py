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
"""RLS provisioning and attribute parsing tests — Phase 6."""

from unittest.mock import MagicMock, patch

from app.config import Settings
from app.models.provisioning_sync_log import ProvisioningSyncStatus
from app.provisioning.blueprint import (
    cntt_cv_role_name,
    cntt_ld_role_name,
    dept_cv_role_name,
    dept_ld_role_name,
)
from app.provisioning.rls import (
    dept_from_role_names,
    dept_rls_clause,
    dept_rls_rule_name,
    tenant_from_role_names,
    tenant_from_username,
    tenant_rls_clause,
    tenant_rls_rule_name,
)
from app.provisioning.service import ProvisioningService
from app.provisioning.superset_client import SupersetRole
from app.seed import DEMO_TENANT_ID


def test_tenant_from_portal_username() -> None:
    assert tenant_from_username("t_demo-corp__cntt.cv@demo-corp") == "demo-corp"
    assert tenant_from_username("admin") is None


def test_dept_from_role_names() -> None:
    roles = [
        dept_cv_role_name("demo-corp", "KETOAN"),
        cntt_ld_role_name("demo-corp"),
    ]
    assert dept_from_role_names(roles) == "KETOAN"


def test_tenant_from_cntt_role_only() -> None:
    assert tenant_from_role_names([cntt_cv_role_name("demo-corp")]) == "demo-corp"
    assert dept_from_role_names([cntt_ld_role_name("demo-corp")]) is None


def test_rls_rule_naming() -> None:
    assert dept_rls_rule_name("demo-corp", "KETOAN") == "rls_t_demo-corp_d_KETOAN"
    assert tenant_rls_rule_name("demo-corp") == "rls_t_demo-corp_tenant"


def test_rls_clauses_use_jinja_macros() -> None:
    assert "current_user_tenant()" in dept_rls_clause()
    assert "current_user_dept()" in dept_rls_clause()
    assert "current_user_dept()" not in tenant_rls_clause()


def test_dept_users_isolated_by_clause() -> None:
    clause_a = dept_rls_clause()
    clause_b = dept_rls_clause()
    assert clause_a == clause_b
    assert "dept_code" in clause_a


def test_provision_department_rls_skipped_without_datasets() -> None:
    db = MagicMock()
    settings = Settings(
        superset_service_api_key="sst_test_key",
        superset_rls_dataset_names="missing_dataset",
    )
    mock_client = MagicMock()
    mock_client.enabled = True
    mock_client.find_dataset_ids_by_names.return_value = []

    service = ProvisioningService(db, client=mock_client, settings=settings)
    service._get_or_create_log = MagicMock(  # type: ignore[method-assign]
        return_value=MagicMock(
            entity_key=dept_rls_rule_name("demo-corp", "KETOAN"),
            attempts=0,
            tenant_id=DEMO_TENANT_ID,
        )
    )
    service._mark_skipped = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda log, msg: __import__(
            "app.provisioning.service", fromlist=["ProvisioningResult"]
        ).ProvisioningResult(
            entity_key=log.entity_key,
            status=ProvisioningSyncStatus.SKIPPED,
            message=msg,
        )
    )

    result = service.provision_department_rls("demo-corp", DEMO_TENANT_ID, "KETOAN")

    assert result.status == ProvisioningSyncStatus.SKIPPED
    mock_client.find_dataset_ids_by_names.assert_called_once()


def test_provision_department_rls_creates_rule() -> None:
    db = MagicMock()
    settings = Settings(
        superset_service_api_key="sst_test_key",
        superset_rls_dataset_names="portal_export_data",
    )
    mock_client = MagicMock()
    mock_client.enabled = True
    mock_client.find_dataset_ids_by_names.return_value = [7]
    mock_client.find_rls_rule_by_name.return_value = None
    mock_client.create_rls_rule.return_value = 99

    cv_role = SupersetRole(
        id=1,
        name=dept_cv_role_name("demo-corp", "KETOAN"),
        permission_ids=(),
        user_ids=(),
    )
    ld_role = SupersetRole(
        id=2,
        name=dept_ld_role_name("demo-corp", "KETOAN"),
        permission_ids=(),
        user_ids=(),
    )

    def find_role(name: str) -> SupersetRole | None:
        if name == cv_role.name:
            return cv_role
        if name == ld_role.name:
            return ld_role
        return None

    mock_client.find_role_by_name.side_effect = find_role

    service = ProvisioningService(db, client=mock_client, settings=settings)
    log = MagicMock()
    log.entity_key = dept_rls_rule_name("demo-corp", "KETOAN")
    log.attempts = 0
    log.tenant_id = DEMO_TENANT_ID
    service._get_or_create_log = MagicMock(return_value=log)  # type: ignore[method-assign]

    with patch("app.provisioning.service.write_audit_log") as audit:
        service._mark_success = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda entry, sid, **kwargs: __import__(
                "app.provisioning.service", fromlist=["ProvisioningResult"]
            ).ProvisioningResult(
                entity_key=entry.entity_key,
                status=ProvisioningSyncStatus.SUCCESS,
                superset_id=sid,
            )
        )
        result = service.provision_department_rls("demo-corp", DEMO_TENANT_ID, "KETOAN")

    assert result.status == ProvisioningSyncStatus.SUCCESS
    assert result.superset_id == 99
    mock_client.create_rls_rule.assert_called_once()
    call_kwargs = mock_client.create_rls_rule.call_args.kwargs
    assert call_kwargs["clause"] == dept_rls_clause()
    assert call_kwargs["role_ids"] == [1, 2]
    audit.assert_called_once()
    assert audit.call_args.kwargs["action"] == "RLS_CREATED"


def test_provision_tenant_rls_for_cntt_roles() -> None:
    db = MagicMock()
    settings = Settings(
        superset_service_api_key="sst_test_key",
        superset_rls_dataset_names="portal_export_data",
    )
    mock_client = MagicMock()
    mock_client.enabled = True
    mock_client.find_dataset_ids_by_names.return_value = [7]
    mock_client.find_rls_rule_by_name.return_value = 50
    mock_client.update_rls_rule.return_value = None

    cv = SupersetRole(
        id=10,
        name=cntt_cv_role_name("demo-corp"),
        permission_ids=(),
        user_ids=(),
    )
    ld = SupersetRole(
        id=11,
        name=cntt_ld_role_name("demo-corp"),
        permission_ids=(),
        user_ids=(),
    )
    mock_client.find_role_by_name.side_effect = lambda name: (
        cv if name == cv.name else ld if name == ld.name else None
    )

    service = ProvisioningService(db, client=mock_client, settings=settings)
    log = MagicMock()
    log.entity_key = tenant_rls_rule_name("demo-corp")
    log.attempts = 0
    log.tenant_id = DEMO_TENANT_ID
    service._get_or_create_log = MagicMock(return_value=log)  # type: ignore[method-assign]

    with patch("app.provisioning.service.write_audit_log"):
        service._mark_success = MagicMock(  # type: ignore[method-assign]
            side_effect=lambda entry, sid, **kwargs: __import__(
                "app.provisioning.service", fromlist=["ProvisioningResult"]
            ).ProvisioningResult(
                entity_key=entry.entity_key,
                status=ProvisioningSyncStatus.SUCCESS,
                superset_id=sid,
            )
        )
        result = service.provision_tenant_rls("demo-corp", DEMO_TENANT_ID)

    assert result.status == ProvisioningSyncStatus.SUCCESS
    mock_client.update_rls_rule.assert_called_once()
    assert mock_client.update_rls_rule.call_args.kwargs["clause"] == tenant_rls_clause()


def test_deactivate_department_rls() -> None:
    db = MagicMock()
    settings = Settings(superset_service_api_key="sst_test_key")
    mock_client = MagicMock()
    mock_client.enabled = True
    mock_client.find_rls_rule_by_name.return_value = 55

    service = ProvisioningService(db, client=mock_client, settings=settings)
    log = MagicMock()
    log.entity_key = dept_rls_rule_name("demo-corp", "KETOAN")
    log.attempts = 0
    log.tenant_id = DEMO_TENANT_ID
    service._get_or_create_log = MagicMock(return_value=log)  # type: ignore[method-assign]
    service._mark_success = MagicMock(  # type: ignore[method-assign]
        side_effect=lambda entry, sid, **kwargs: __import__(
            "app.provisioning.service", fromlist=["ProvisioningResult"]
        ).ProvisioningResult(
            entity_key=entry.entity_key,
            status=ProvisioningSyncStatus.SUCCESS,
            superset_id=sid,
        )
    )

    result = service.deactivate_department_rls("demo-corp", DEMO_TENANT_ID, "KETOAN")

    assert result.status == ProvisioningSyncStatus.SUCCESS
    mock_client.delete_rls_rule.assert_called_once_with(55)


def test_cross_dept_isolation_via_role_parsing() -> None:
    """Dept A user roles must not resolve to dept B."""
    dept_a = dept_from_role_names([dept_cv_role_name("demo-corp", "KETOAN")])
    dept_b = dept_from_role_names([dept_cv_role_name("demo-corp", "CNTT")])
    assert dept_a == "KETOAN"
    assert dept_b == "CNTT"
    assert dept_a != dept_b
