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
"""Portal FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.templates import router as templates_router
from app.api.ai import router as ai_router
from app.api.auth import router as auth_router
from app.api.departments import router as departments_router
from app.api.health import router as health_router
from app.api.pki import router as pki_router
from app.api.sso import router as sso_router
from app.api.platform import router as platform_router
from app.api.tenants import router as tenants_router
from app.api.provisioning import router as provisioning_router
from app.api.users import router as users_router
from app.config import get_settings
from app.provisioning.handlers import bootstrap_existing_tenants, register_provisioning_handlers

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    register_provisioning_handlers()
    bootstrap_existing_tenants()
    yield


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

origins = [origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(pki_router)
app.include_router(sso_router)
app.include_router(tenants_router)
app.include_router(platform_router)
app.include_router(departments_router)
app.include_router(users_router)
app.include_router(provisioning_router)
app.include_router(ai_router)
app.include_router(templates_router)
