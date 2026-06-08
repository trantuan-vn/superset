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
"""Department-facing template list API — Phase 10."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.schemas import TemplateResponse
from app.auth.dependencies import get_current_user_with_dept_roles, require_capability
from app.auth.policy import Capability
from app.db import get_db
from app.models.user import User
from app.templates.access import list_dept_accessible_templates, shared_department_rows
from app.templates.service import TemplateError, template_to_dict

router = APIRouter(prefix="/dept", tags=["dept"])


def _handle_template_error(exc: TemplateError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


@router.get("/templates", response_model=list[TemplateResponse])
def list_dept_templates_api(
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(require_capability(Capability.DEPT_TEMPLATES))],
) -> list[TemplateResponse]:
    templates = list_dept_accessible_templates(db, user)
    creator_ids = {template.created_by for template in templates}
    names: dict = {}
    if creator_ids:
        from app.models.user import User as UserModel

        users = db.scalars(
            select(UserModel).where(UserModel.id.in_(creator_ids))
        ).all()
        names = {item.id: item.display_name for item in users}

    return [
        TemplateResponse(
            **template_to_dict(
                template,
                creator_name=names.get(template.created_by),
                shared_departments=shared_department_rows(db, template),
            )
        )
        for template in templates
    ]
