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
"""Fetch approved export rows from Superset with user-scoped RLS/Jinja."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.config import Settings, get_settings
from app.models.export_template import ExportTemplate
from app.models.tenant import Tenant
from app.models.user import User
from app.superset.launch import SupersetLaunchTarget, superset_deep_link
from app.superset.launch_auth import mint_launch_jwt

_DEFAULT_ROW_LIMIT = 10_000


class ExportDataError(Exception):
    """Raised when Superset export data cannot be loaded."""

    def __init__(self, message: str, *, status_code: int = 502) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _launch_resource(template: ExportTemplate) -> tuple[SupersetLaunchTarget, int]:
    if template.superset_dashboard_id is not None:
        return SupersetLaunchTarget.DASHBOARD_VIEW, template.superset_dashboard_id
    if template.superset_dataset_id is not None:
        return SupersetLaunchTarget.DATASET, template.superset_dataset_id
    raise ExportDataError(
        "Template is not linked to a Superset dataset",
        status_code=409,
    )


def _establish_user_session(
    *,
    settings: Settings,
    user: User,
    tenant: Tenant,
    template: ExportTemplate,
) -> httpx.Client:
    """Log into Superset as the Portal user via Launch Bridge and return a client."""
    target, resource_id = _launch_resource(template)
    launch_jwt = mint_launch_jwt(
        user=user,
        tenant=tenant,
        target=target,
        resource_id=resource_id,
    )
    base_url = settings.superset_internal_url.rstrip("/")
    next_path = superset_deep_link(target, resource_id)
    login_url = (
        f"{base_url}/login/?portal_launch={quote(launch_jwt, safe='')}"
        f"&next={quote(next_path, safe='')}"
    )

    client = httpx.Client(
        timeout=settings.provisioning_http_timeout,
        follow_redirects=True,
    )
    try:
        response = client.get(login_url)
    except httpx.HTTPError as exc:
        client.close()
        raise ExportDataError(f"Superset unreachable: {exc}") from exc

    if response.status_code >= 400:
        client.close()
        raise ExportDataError(
            f"Superset launch login failed ({response.status_code})",
        )

    return client


def _dataset_columns(client: httpx.Client, base_url: str, dataset_id: int) -> list[str]:
    response = client.get(f"{base_url}/api/v1/dataset/{dataset_id}")
    if response.status_code == 404:
        raise ExportDataError("Superset dataset not found", status_code=404)
    if response.status_code >= 400:
        raise ExportDataError(
            f"Failed to load Superset dataset ({response.status_code})",
        )

    payload = response.json()
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        raise ExportDataError("Unexpected Superset dataset response")

    columns: list[str] = []
    for column in result.get("columns") or []:
        if isinstance(column, dict):
            name = column.get("column_name")
            if name:
                columns.append(str(name))
    if not columns:
        raise ExportDataError("Superset dataset has no columns")
    return columns


def _chart_data_payload(
    *,
    dataset_id: int,
    columns: list[str],
    row_limit: int,
) -> dict[str, Any]:
    return {
        "datasource": {"id": dataset_id, "type": "table"},
        "queries": [
            {
                "columns": columns,
                "metrics": [],
                "orderby": [],
                "row_limit": row_limit,
            }
        ],
        "result_format": "json",
        "result_type": "full",
    }


def _parse_chart_data_response(payload: dict[str, Any]) -> dict[str, Any]:
    results = payload.get("result")
    if not isinstance(results, list) or not results:
        raise ExportDataError("Superset returned no query results")

    block = results[0]
    if not isinstance(block, dict):
        raise ExportDataError("Unexpected Superset chart data response")

    if block.get("error"):
        raise ExportDataError(f"Superset query failed: {block['error']}")

    colnames = [str(name) for name in block.get("colnames") or []]
    raw_rows = block.get("data") or []
    rows: list[dict[str, Any]] = []
    for raw in raw_rows:
        if not isinstance(raw, dict):
            continue
        rows.append({column: raw.get(column) for column in colnames})

    rowcount = block.get("sql_rowcount")
    if rowcount is None:
        rowcount = len(rows)

    return {
        "columns": colnames,
        "rows": rows,
        "row_count": int(rowcount),
        "truncated": len(rows) < int(rowcount),
        "mock": False,
    }


def fetch_template_query_data(
    *,
    user: User,
    tenant: Tenant,
    template: ExportTemplate,
    row_limit: int = _DEFAULT_ROW_LIMIT,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """
    Execute the template virtual dataset on Superset as ``user``.

    Applies Jinja macros (``current_user_tenant`` / ``current_user_dept``) and
    row-level security exactly as the dashboard would for that user.
    """
    app_settings = settings or get_settings()
    dataset_id = template.superset_dataset_id
    if dataset_id is None:
        raise ExportDataError(
            "Template is not linked to a Superset dataset",
            status_code=409,
        )

    client = _establish_user_session(
        settings=app_settings,
        user=user,
        tenant=tenant,
        template=template,
    )
    base_url = app_settings.superset_internal_url.rstrip("/")

    try:
        columns = _dataset_columns(client, base_url, dataset_id)
        response = client.post(
            f"{base_url}/api/v1/chart/data",
            json=_chart_data_payload(
                dataset_id=dataset_id,
                columns=columns,
                row_limit=row_limit,
            ),
        )
    except httpx.HTTPError as exc:
        raise ExportDataError(f"Superset unreachable: {exc}") from exc
    finally:
        client.close()

    if response.status_code >= 400:
        detail = response.text[:500]
        raise ExportDataError(
            f"Superset export query failed ({response.status_code}): {detail}",
        )

    payload = response.json()
    if not isinstance(payload, dict):
        raise ExportDataError("Unexpected Superset chart data response")
    return _parse_chart_data_response(payload)
