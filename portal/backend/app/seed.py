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
"""Idempotent demo seed data for Phase 1."""

import uuid

from sqlalchemy import select

from app.auth.password import hash_password
from app.db import SessionLocal
from app.models.tenant import Tenant, TenantSettings
from app.models.user import SystemRole, User, UserStatus

DEMO_TENANT_ID = uuid.UUID("a0000000-0000-4000-8000-000000000001")
PLATFORM_TENANT_ID = uuid.UUID("a0000000-0000-4000-8000-000000000010")
DEMO_PASSWORD = "Pass123!"

DEMO_USERS: list[dict[str, str | SystemRole]] = [
    {
        "username": "admin@demo-corp",
        "email": "admin@demo-corp",
        "display_name": "Tenant Admin",
        "system_role": SystemRole.TENANT_ADMIN,
    },
    {
        "username": "cntt.cv@demo-corp",
        "email": "cntt.cv@demo-corp",
        "display_name": "CNTT Chuyên viên",
        "system_role": SystemRole.CNTT_CHUYENVIEN,
    },
    {
        "username": "cntt.ld@demo-corp",
        "email": "cntt.ld@demo-corp",
        "display_name": "CNTT Lãnh đạo",
        "system_role": SystemRole.CNTT_LANHDAO,
    },
]


def seed_demo_data() -> None:
    """Insert demo tenant and users when missing."""
    db = SessionLocal()
    try:
        tenant = db.get(Tenant, DEMO_TENANT_ID)
        if tenant is None:
            tenant = Tenant(
                id=DEMO_TENANT_ID,
                slug="demo-corp",
                name="Demo Corporation",
            )
            db.add(tenant)
            db.flush()

        settings = db.get(TenantSettings, DEMO_TENANT_ID)
        if settings is None:
            settings = TenantSettings(
                tenant_id=DEMO_TENANT_ID,
                branding={
                    "app_name": "Portal Kết xuất",
                    "primary_color": "#1677ff",
                },
            )
            db.add(settings)

        password_hash = hash_password(DEMO_PASSWORD)
        for spec in DEMO_USERS:
            username = str(spec["username"])
            existing = db.scalar(
                select(User).where(
                    User.tenant_id == DEMO_TENANT_ID,
                    User.username == username,
                )
            )
            if existing is None:
                db.add(
                    User(
                        tenant_id=DEMO_TENANT_ID,
                        username=username,
                        email=str(spec["email"]),
                        display_name=str(spec["display_name"]),
                        password_hash=password_hash,
                        system_role=spec["system_role"],  # type: ignore[arg-type]
                        status=UserStatus.ACTIVE,
                    )
                )

        platform = db.get(Tenant, PLATFORM_TENANT_ID)
        if platform is None:
            platform = Tenant(
                id=PLATFORM_TENANT_ID,
                slug="platform",
                name="Platform Operations",
            )
            db.add(platform)
            db.flush()

        platform_settings = db.get(TenantSettings, PLATFORM_TENANT_ID)
        if platform_settings is None:
            platform_settings = TenantSettings(
                tenant_id=PLATFORM_TENANT_ID,
                branding={"app_name": "Portal — Platform"},
            )
            db.add(platform_settings)

        platform_admin = db.scalar(
            select(User).where(
                User.tenant_id == PLATFORM_TENANT_ID,
                User.username == "admin@platform",
            )
        )
        if platform_admin is None:
            db.add(
                User(
                    tenant_id=PLATFORM_TENANT_ID,
                    username="admin@platform",
                    email="admin@platform",
                    display_name="Platform Administrator",
                    password_hash=hash_password(DEMO_PASSWORD),
                    system_role=SystemRole.PLATFORM_ADMIN,
                    status=UserStatus.ACTIVE,
                )
            )

        db.commit()
        print(
            "Demo seed complete: demo-corp / Pass123! | platform admin: platform / admin@platform / Pass123!"
        )
    finally:
        db.close()


if __name__ == "__main__":
    seed_demo_data()
