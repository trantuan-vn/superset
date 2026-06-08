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
"""Superset deep-link targets opened via Launch Bridge."""

from __future__ import annotations

import enum


class SupersetLaunchTarget(str, enum.Enum):
    """Resource Portal opens in a new Superset browser tab."""

    DATASET = "dataset"
    DASHBOARD_DESIGN = "dashboard_design"
    DASHBOARD_REVIEW = "dashboard_review"
    DASHBOARD_VIEW = "dashboard_view"


def superset_deep_link(target: SupersetLaunchTarget, resource_id: int) -> str:
    """Return a Superset path (with leading slash) for the given resource."""
    if target == SupersetLaunchTarget.DATASET:
        return f"/explore/?datasource_type=table&datasource_id={resource_id}"
    if target == SupersetLaunchTarget.DASHBOARD_DESIGN:
        return f"/superset/dashboard/{resource_id}/?edit=true"
    if target == SupersetLaunchTarget.DASHBOARD_REVIEW:
        return f"/superset/dashboard/{resource_id}/?standalone=1"
    if target == SupersetLaunchTarget.DASHBOARD_VIEW:
        return f"/superset/dashboard/{resource_id}/?standalone=1"
    raise ValueError(f"Unsupported launch target: {target}")
