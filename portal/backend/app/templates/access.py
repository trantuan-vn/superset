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
"""Resolve which departments may access a published template."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.policy import dept_roles
from app.models.department import Department, DepartmentStatus
from app.models.export_template import ExportTemplate, TemplateShareMode, TemplateStatus
from app.models.template_share import TemplateDepartmentShare
from app.models.user import User


def primary_department_id(user: User) -> uuid.UUID | None:
    """Return the user's assigned department (dept_user has exactly one)."""
    roles = dept_roles(user)
    if not roles:
        return None
    assignment = roles[0]
    if assignment.department is not None:
        return assignment.department.id
    return assignment.department_id


def shared_department_rows(
    db: Session,
    template: ExportTemplate,
) -> list[dict[str, Any]]:
    """Departments allowed to use a published template."""
    if template.status != TemplateStatus.PUBLISHED or template.share_mode is None:
        return []

    if template.share_mode == TemplateShareMode.ALL:
        departments = db.scalars(
            select(Department).where(
                Department.tenant_id == template.tenant_id,
                Department.status == DepartmentStatus.ACTIVE,
            )
        ).all()
    else:
        share_rows = db.scalars(
            select(TemplateDepartmentShare).where(
                TemplateDepartmentShare.template_id == template.id
            )
        ).all()
        dept_ids = {row.department_id for row in share_rows}
        if not dept_ids:
            return []
        departments = db.scalars(
            select(Department).where(Department.id.in_(dept_ids))
        ).all()

    return [
        {
            "id": str(dept.id),
            "code": dept.code,
            "name": dept.name,
        }
        for dept in departments
    ]


def template_accessible_by_department(
    db: Session,
    template: ExportTemplate,
    department_id: uuid.UUID,
) -> bool:
    if template.status != TemplateStatus.PUBLISHED or template.share_mode is None:
        return False
    if template.share_mode == TemplateShareMode.ALL:
        dept = db.get(Department, department_id)
        return (
            dept is not None
            and dept.tenant_id == template.tenant_id
            and dept.status == DepartmentStatus.ACTIVE
        )
    share = db.scalar(
        select(TemplateDepartmentShare).where(
            TemplateDepartmentShare.template_id == template.id,
            TemplateDepartmentShare.department_id == department_id,
        )
    )
    return share is not None


def list_dept_accessible_templates(db: Session, user: User) -> list[ExportTemplate]:
    """Published templates shared with the user's department."""
    department_id = primary_department_id(user)
    if department_id is None:
        return []

    published = db.scalars(
        select(ExportTemplate).where(
            ExportTemplate.tenant_id == user.tenant_id,
            ExportTemplate.status == TemplateStatus.PUBLISHED,
        )
    ).all()

    return [
        template
        for template in published
        if template_accessible_by_department(db, template, department_id)
    ]
