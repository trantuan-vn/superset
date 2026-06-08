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

from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import httpx

from app.export.superset_data import ExportDataError, fetch_template_query_data, _parse_chart_data_response


def test_parse_chart_data_response_maps_rows() -> None:
    payload = {
        "result": [
            {
                "colnames": ["id", "metric_name", "metric_value"],
                "data": [
                    {"id": 1, "metric_name": "revenue", "metric_value": 1000.0},
                    {"id": 2, "metric_name": "expense", "metric_value": 400.0},
                ],
                "sql_rowcount": 2,
            }
        ]
    }
    parsed = _parse_chart_data_response(payload)
    assert parsed["mock"] is False
    assert parsed["columns"] == ["id", "metric_name", "metric_value"]
    assert parsed["rows"][1]["metric_name"] == "expense"


def test_fetch_template_query_data_requires_dataset_id() -> None:
    user = MagicMock()
    tenant = MagicMock()
    template = MagicMock()
    template.superset_dataset_id = None
    template.superset_dashboard_id = None

    try:
        fetch_template_query_data(user=user, tenant=tenant, template=template)
        raise AssertionError("expected ExportDataError")
    except ExportDataError as exc:
        assert exc.status_code == 409


def test_fetch_template_query_data_uses_launch_session_and_chart_data() -> None:
    user = MagicMock()
    user.id = uuid.uuid4()
    tenant = MagicMock()
    tenant.id = uuid.uuid4()
    tenant.slug = "demo-corp"

    template = MagicMock()
    template.superset_dataset_id = 25
    template.superset_dashboard_id = 10

    dataset_response = httpx.Response(
        200,
        json={
            "result": {
                "columns": [
                    {"column_name": "id"},
                    {"column_name": "metric_name"},
                    {"column_name": "metric_value"},
                ]
            }
        },
    )
    chart_response = httpx.Response(
        200,
        json={
            "result": [
                {
                    "colnames": ["id", "metric_name", "metric_value"],
                    "data": [{"id": 2, "metric_name": "expense", "metric_value": 400.0}],
                    "sql_rowcount": 1,
                }
            ]
        },
    )

    mock_client = MagicMock()
    mock_client.get.return_value = httpx.Response(200, request=httpx.Request("GET", "http://x/login"))
    mock_client.post.return_value = chart_response
    mock_client.__enter__ = MagicMock(return_value=mock_client)
    mock_client.__exit__ = MagicMock(return_value=False)

    with (
        patch("app.export.superset_data.mint_launch_jwt", return_value="jwt"),
        patch("app.export.superset_data.httpx.Client", return_value=mock_client),
        patch(
            "app.export.superset_data._dataset_columns",
            return_value=["id", "metric_name", "metric_value"],
        ),
    ):
        result = fetch_template_query_data(user=user, tenant=tenant, template=template)

    assert result["mock"] is False
    assert result["rows"][0]["metric_name"] == "expense"
    mock_client.get.assert_called_once()
    mock_client.post.assert_called_once()
