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
"""Department and user administration — Phase 4."""

import re
import uuid
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.audit.service import write_audit_log
from app.auth.password import hash_password
from app.auth.policy import can_assign_system_role, can_modify_user
from app.departments.events import DepartmentCreated, emit_department_created
from app.models.department import Department, DepartmentStatus, DeptRole, UserDeptRole
from app.models.tenant import Tenant
from app.models.user import SystemRole, User, UserStatus

_CODE_PATTERN = re.compile(r"^[A-Z0-9_]{2,64}$")


class DeptError(Exception):
    """Department or user admin error with HTTP status code."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class DepartmentListFilters:
    search: str | None = None
    status: DepartmentStatus | None = None


def _normalize_code(code: str) -> str:
    normalized = code.strip().upper()
    if not _CODE_PATTERN.match(normalized):
        raise DeptError(
            "Department code must be 2–64 uppercase letters, digits, or underscores",
            status_code=422,
        )
    return normalized


def list_departments(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    filters: DepartmentListFilters | None = None,
) -> list[Department]:
    stmt = select(Department).where(Department.tenant_id == tenant_id)
    if filters:
        if filters.status is not None:
            stmt = stmt.where(Department.status == filters.status)
        if filters.search:
            term = f"%{filters.search.strip()}%"
            stmt = stmt.where(
                or_(Department.code.ilike(term), Department.name.ilike(term))
            )
    stmt = stmt.order_by(Department.code)
    return list(db.scalars(stmt).all())


def get_department(
    db: Session, tenant_id: uuid.UUID, department_id: uuid.UUID
) -> Department:
    dept = db.scalar(
        select(Department).where(
            Department.id == department_id,
            Department.tenant_id == tenant_id,
        )
    )
    if dept is None:
        raise DeptError("Department not found", status_code=404)
    return dept


def create_department(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    code: str,
    name: str,
    actor: User,
    ip_address: str | None = None,
) -> Department:
    normalized_code = _normalize_code(code)
    name_clean = name.strip()
    if not name_clean:
        raise DeptError("Department name is required", status_code=422)

    existing = db.scalar(
        select(Department).where(
            Department.tenant_id == tenant_id,
            Department.code == normalized_code,
        )
    )
    if existing is not None:
        raise DeptError(
            f"Department code '{normalized_code}' already exists",
            status_code=409,
        )

    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise DeptError("Tenant not found", status_code=404)

    dept = Department(
        tenant_id=tenant_id,
        code=normalized_code,
        name=name_clean,
        status=DepartmentStatus.ACTIVE,
    )
    db.add(dept)
    db.commit()
    db.refresh(dept)

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="DEPT_CREATED",
        entity_type="department",
        entity_id=str(dept.id),
        actor_id=actor.id,
        payload={"code": dept.code, "name": dept.name},
        ip_address=ip_address,
    )

    emit_department_created(
        DepartmentCreated(department=dept, tenant_slug=tenant.slug)
    )
    return dept


def update_department(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    department_id: uuid.UUID,
    name: str | None = None,
    status: DepartmentStatus | None = None,
    actor: User,
    ip_address: str | None = None,
) -> Department:
    dept = get_department(db, tenant_id, department_id)
    changes: dict[str, str] = {}

    if name is not None:
        name_clean = name.strip()
        if not name_clean:
            raise DeptError("Department name is required", status_code=422)
        if dept.name != name_clean:
            changes["name"] = name_clean
            dept.name = name_clean

    if status is not None and dept.status != status:
        changes["status"] = status.value
        dept.status = status

    if not changes:
        return dept

    db.commit()
    db.refresh(dept)

    action = "DEPT_DEACTIVATED" if status == DepartmentStatus.INACTIVE else "DEPT_UPDATED"
    write_audit_log(
        db,
        tenant_id=tenant_id,
        action=action,
        entity_type="department",
        entity_id=str(dept.id),
        actor_id=actor.id,
        payload=changes,
        ip_address=ip_address,
    )
    return dept


def department_to_dict(dept: Department) -> dict[str, str]:
    return {
        "id": str(dept.id),
        "tenant_id": str(dept.tenant_id),
        "code": dept.code,
        "name": dept.name,
        "status": dept.status.value,
    }


def list_users(
    db: Session,
    tenant_id: uuid.UUID,
    *,
    search: str | None = None,
    system_role: SystemRole | None = None,
) -> list[User]:
    stmt = (
        select(User)
        .options(
            joinedload(User.dept_roles).joinedload(UserDeptRole.department)
        )
        .where(User.tenant_id == tenant_id)
    )
    if system_role is not None:
        stmt = stmt.where(User.system_role == system_role)
    if search:
        term = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                User.username.ilike(term),
                User.email.ilike(term),
                User.display_name.ilike(term),
            )
        )
    stmt = stmt.order_by(User.display_name)
    return list(db.scalars(stmt).unique().all())


def get_user_in_tenant(
    db: Session, tenant_id: uuid.UUID, user_id: uuid.UUID
) -> User:
    user = db.scalar(
        select(User)
        .options(
            joinedload(User.dept_roles).joinedload(UserDeptRole.department)
        )
        .where(User.id == user_id, User.tenant_id == tenant_id)
    )
    if user is None:
        raise DeptError("User not found", status_code=404)
    return user


def create_user(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    username: str,
    email: str,
    display_name: str,
    password: str,
    system_role: SystemRole,
    actor: User,
    ip_address: str | None = None,
) -> User:
    if not can_assign_system_role(actor, system_role):
        raise DeptError(
            "You cannot assign this account type",
            status_code=403,
        )
    if system_role == SystemRole.PLATFORM_ADMIN:
        raise DeptError("Cannot create platform_admin via tenant API", status_code=403)

    username_norm = username.strip().lower()
    email_norm = email.strip().lower()
    display_clean = display_name.strip()

    if not username_norm or not email_norm or not display_clean:
        raise DeptError("Username, email, and display name are required", status_code=422)
    if len(password) < 8:
        raise DeptError("Password must be at least 8 characters", status_code=422)

    existing = db.scalar(
        select(User).where(
            User.tenant_id == tenant_id,
            or_(User.username == username_norm, User.email == email_norm),
        )
    )
    if existing is not None:
        raise DeptError("Username or email already exists in this tenant", status_code=409)

    user = User(
        tenant_id=tenant_id,
        username=username_norm,
        email=email_norm,
        display_name=display_clean,
        password_hash=hash_password(password),
        system_role=system_role,
        status=UserStatus.ACTIVE,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="USER_CREATED",
        entity_type="user",
        entity_id=str(user.id),
        actor_id=actor.id,
        payload={"username": user.username, "system_role": user.system_role.value},
        ip_address=ip_address,
    )
    return get_user_in_tenant(db, tenant_id, user.id)


def update_user(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    display_name: str | None = None,
    email: str | None = None,
    status: UserStatus | None = None,
    actor: User,
    ip_address: str | None = None,
) -> User:
    user = get_user_in_tenant(db, tenant_id, user_id)
    if not can_modify_user(actor, user):
        raise DeptError("You cannot modify this user", status_code=403)

    changes: dict[str, str] = {}

    if display_name is not None:
        clean = display_name.strip()
        if not clean:
            raise DeptError("Display name is required", status_code=422)
        if user.display_name != clean:
            changes["display_name"] = clean
            user.display_name = clean

    if email is not None:
        email_norm = email.strip().lower()
        if not email_norm:
            raise DeptError("Email is required", status_code=422)
        conflict = db.scalar(
            select(User).where(
                User.tenant_id == tenant_id,
                User.email == email_norm,
                User.id != user_id,
            )
        )
        if conflict is not None:
            raise DeptError("Email already in use", status_code=409)
        if user.email != email_norm:
            changes["email"] = email_norm
            user.email = email_norm

    if status is not None and user.status != status:
        changes["status"] = status.value
        user.status = status

    if not changes:
        return user

    db.commit()
    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="USER_UPDATED",
        entity_type="user",
        entity_id=str(user.id),
        actor_id=actor.id,
        payload=changes,
        ip_address=ip_address,
    )
    return get_user_in_tenant(db, tenant_id, user_id)


def assign_dept_role(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    department_id: uuid.UUID,
    role: DeptRole,
    actor: User,
    ip_address: str | None = None,
) -> User:
    """Assign or update a user's role within a department.

    Policy: ``dept_user`` may belong to exactly one department. CNTT roles
    do not require department assignments.
    """
    user = get_user_in_tenant(db, tenant_id, user_id)
    if not can_modify_user(actor, user):
        raise DeptError("You cannot modify this user", status_code=403)
    dept = get_department(db, tenant_id, department_id)

    if dept.status != DepartmentStatus.ACTIVE:
        raise DeptError("Cannot assign roles to an inactive department", status_code=400)

    if user.system_role != SystemRole.DEPT_USER:
        raise DeptError(
            "Only dept_user accounts can be assigned department roles",
            status_code=422,
        )

    if user.dept_roles:
        other_dept = next(
            (r for r in user.dept_roles if r.department_id != department_id),
            None,
        )
        if other_dept is not None:
            raise DeptError(
                "Each dept_user may belong to one department only. "
                "Remove the existing assignment first.",
                status_code=409,
            )

    existing = db.scalar(
        select(UserDeptRole).where(
            UserDeptRole.user_id == user_id,
            UserDeptRole.department_id == department_id,
        )
    )
    if existing is not None:
        existing.role = role
    else:
        db.add(
            UserDeptRole(
                user_id=user_id,
                department_id=department_id,
                role=role,
            )
        )

    db.commit()

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="USER_DEPT_ROLE_ASSIGNED",
        entity_type="user",
        entity_id=str(user.id),
        actor_id=actor.id,
        payload={
            "department_id": str(department_id),
            "department_code": dept.code,
            "role": role.value,
        },
        ip_address=ip_address,
    )
    return get_user_in_tenant(db, tenant_id, user_id)


def remove_dept_role(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    department_id: uuid.UUID,
    actor: User,
    ip_address: str | None = None,
) -> User:
    user = get_user_in_tenant(db, tenant_id, user_id)
    if not can_modify_user(actor, user):
        raise DeptError("You cannot modify this user", status_code=403)
    assignment = db.scalar(
        select(UserDeptRole).where(
            UserDeptRole.user_id == user_id,
            UserDeptRole.department_id == department_id,
        )
    )
    if assignment is None:
        raise DeptError("Department role assignment not found", status_code=404)

    db.delete(assignment)
    db.commit()

    write_audit_log(
        db,
        tenant_id=tenant_id,
        action="USER_DEPT_ROLE_REMOVED",
        entity_type="user",
        entity_id=str(user.id),
        actor_id=actor.id,
        payload={"department_id": str(department_id)},
        ip_address=ip_address,
    )
    return get_user_in_tenant(db, tenant_id, user_id)


def user_dept_roles_for_response(user: User) -> list[dict[str, str]]:
    roles: list[dict[str, str]] = []
    for assignment in user.dept_roles:
        dept = assignment.department
        if dept is None:
            continue
        roles.append(
            {
                "department_id": str(dept.id),
                "department_code": dept.code,
                "department_name": dept.name,
                "role": assignment.role.value,
            }
        )
    return roles


def user_to_dict(user: User) -> dict[str, object]:
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "display_name": user.display_name,
        "system_role": user.system_role.value,
        "status": user.status.value,
        "departments": user_dept_roles_for_response(user),
    }


def load_user_dept_roles(db: Session, user_id: uuid.UUID) -> list[dict[str, str]]:
    user = db.scalar(
        select(User)
        .options(
            joinedload(User.dept_roles).joinedload(UserDeptRole.department)
        )
        .where(User.id == user_id)
    )
    if user is None:
        return []
    return user_dept_roles_for_response(user)


def count_active_departments(db: Session, tenant_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Department)
        .where(
            Department.tenant_id == tenant_id,
            Department.status == DepartmentStatus.ACTIVE,
        )
    ) or 0
