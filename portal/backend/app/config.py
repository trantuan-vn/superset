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
"""Portal application configuration."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings for the Portal backend."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Portal Kết xuất"
    app_env: str = "development"
    database_url: str = (
        "postgresql://portal:portal@localhost:5433/portal"
    )
    redis_url: str = "redis://localhost:6379/0"
    session_secret: str = "change-me-in-production-use-64-random-bytes"
    session_ttl_hours: int = 8
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    max_login_attempts: int = 5
    login_lockout_minutes: int = 30
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    portal_public_base_url: str = "http://localhost:8000"
    ldap_bind_password: str = "admin"
    oidc_client_secret: str = "portal-dev-secret-change-in-prod"
    frontend_base_url: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
