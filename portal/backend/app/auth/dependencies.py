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
"""FastAPI dependencies for session authentication."""

import uuid
from collections.abc import Callable
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.auth.policy import Capability, has_capability
from app.auth.session import SESSION_COOKIE_NAME, SessionData, get_session
from app.db import get_db
from app.models.department import UserDeptRole
from app.models.user import SystemRole, User, UserStatus


def get_session_id(
    portal_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE_NAME)] = None,
) -> str:
    if not portal_session:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    session = get_session(portal_session)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    return portal_session


def get_session_data(
    session_id: Annotated[str, Depends(get_session_id)],
) -> SessionData:
    session = get_session(session_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired",
        )
    return session


def get_current_user(
    session: Annotated[SessionData, Depends(get_session_data)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    user = db.scalar(select(User).where(User.id == uuid.UUID(session.user_id)))
    if user is None or user.status != UserStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )
    if str(user.tenant_id) != session.tenant_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant mismatch",
        )
    return user


def get_current_user_with_dept_roles(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> User:
    """Load department role assignments for authorization checks."""
    loaded = db.scalar(
        select(User)
        .options(joinedload(User.dept_roles).joinedload(UserDeptRole.department))
        .where(User.id == user.id)
    )
    if loaded is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return loaded


def require_capability(
    capability: Capability,
) -> Callable[..., User]:
    def _dependency(
        user: Annotated[User, Depends(get_current_user_with_dept_roles)],
    ) -> User:
        if not has_capability(user, capability):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return _dependency


def require_tenant_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not has_capability(user, Capability.TENANT_SETTINGS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tenant administrator access required",
        )
    return user


def require_iam_admin(
    user: Annotated[User, Depends(get_current_user_with_dept_roles)],
) -> User:
    if not has_capability(user, Capability.IAM_ADMIN):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )
    return user


# Backward-compatible alias used by Phase 4 API routes
require_tenant_admin_or_cntt_lanhdao = require_iam_admin


def require_platform_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if not has_capability(user, Capability.PLATFORM_TENANTS):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform administrator access required",
        )
    return user
