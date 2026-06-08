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
"""Persist template share scope in Portal DB."""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.department import Department, DepartmentStatus
from app.models.export_template import ExportTemplate, TemplateShareMode
from app.models.template_share import TemplateDepartmentShare


class ShareError(Exception):
    def __init__(self, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def resolve_share_departments(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    share_mode: TemplateShareMode,
    department_ids: list[uuid.UUID] | None,
) -> list[Department]:
    """Return active departments included in the share scope."""
    if share_mode == TemplateShareMode.SELECTED:
        if not department_ids:
            raise ShareError(
                "At least one department is required for SELECTED share mode",
                status_code=422,
            )
        departments = list(
            db.scalars(
                select(Department).where(
                    Department.tenant_id == tenant_id,
                    Department.id.in_(department_ids),
                    Department.status == DepartmentStatus.ACTIVE,
                )
            ).all()
        )
        if len(departments) != len(set(department_ids)):
            raise ShareError("One or more departments are invalid", status_code=422)
        return departments

    return list(
        db.scalars(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.status == DepartmentStatus.ACTIVE,
            )
        ).all()
    )


def replace_template_shares(
    db: Session,
    template: ExportTemplate,
    *,
    share_mode: TemplateShareMode,
    departments: list[Department],
    shared_by: uuid.UUID,
) -> None:
    """Update share_mode and department share rows for a published template."""
    template.share_mode = share_mode
    template.share_scope_version = (template.share_scope_version or 0) + 1
    db.execute(
        delete(TemplateDepartmentShare).where(
            TemplateDepartmentShare.template_id == template.id
        )
    )
    if share_mode == TemplateShareMode.SELECTED:
        for dept in departments:
            db.add(
                TemplateDepartmentShare(
                    template_id=template.id,
                    department_id=dept.id,
                    shared_by=shared_by,
                )
            )
