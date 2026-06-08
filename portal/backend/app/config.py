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
    pki_pending_session_minutes: int = 30
    session_cookie_secure: bool = False
    session_cookie_samesite: str = "lax"
    max_login_attempts: int = 5
    login_lockout_minutes: int = 30
    cors_origins: str = "http://localhost:5173,http://localhost:3000"
    portal_public_base_url: str = "http://localhost:8000"
    ldap_bind_password: str = "admin"
    oidc_client_secret: str = "portal-dev-secret-change-in-prod"
    frontend_base_url: str = "http://localhost:3000"
    pki_root_ca_path: str | None = None
    superset_internal_url: str = "http://localhost:8088"
    superset_public_url: str = "http://localhost:8088"
    superset_service_username: str = "portal_provisioner"
    superset_service_api_key: str = ""
    # Virtual dataset target database (Superset database connection id)
    superset_template_database_id: int = 1
    # Launch Bridge — short-lived JWT for auto-login from Portal (§1.3, Phase 8)
    superset_launch_jwt_secret: str = ""
    superset_launch_jwt_ttl_seconds: int = 120
    provisioning_max_retries: int = 5
    provisioning_retry_delay_seconds: int = 60
    provisioning_http_timeout: float = 30.0
    # Phase 6 — comma-separated Superset dataset names for RLS attachment
    superset_rls_dataset_names: str = "portal_export_data"
    # Phase 7 — AI rate limit (per user, rolling window)
    ai_rate_limit_per_hour: int = 30
    ai_rate_limit_window_seconds: int = 3600
    # Phase 7 — MCP JWT (HS256 shared secret with Superset MCP_AUTH_ENABLED)
    mcp_jwt_secret: str = "change-me-mcp-jwt-secret-in-production"
    mcp_jwt_issuer: str = "portal"
    mcp_jwt_audience: str = "superset-mcp"
    mcp_jwt_algorithm: str = "HS256"
    mcp_jwt_ttl_minutes: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()
