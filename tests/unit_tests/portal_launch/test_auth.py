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
"""Portal Launch Bridge auth helpers."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pytest
from flask import Flask

from superset.portal_launch.auth import (
    decode_portal_launch_token,
    safe_next_path,
    try_portal_launch_login,
)


@pytest.fixture
def launch_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        PORTAL_LAUNCH_ENABLED=True,
        PORTAL_LAUNCH_JWT_SECRET="test-launch-secret",
        PORTAL_LAUNCH_JWT_ISSUER="portal",
        PORTAL_LAUNCH_JWT_AUDIENCE="superset-launch",
        PORTAL_LAUNCH_JWT_ALGORITHM="HS256",
        SECRET_KEY="test",
    )
    return app


def _mint_token(
    *,
    secret: str = "test-launch-secret",
    sub: str = "t_demo-corp__cntt.cv@demo-corp",
    issuer: str = "portal",
) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "iss": issuer,
        "sub": sub,
        "aud": "superset-launch",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=60)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def test_safe_next_path_allows_relative() -> None:
    assert safe_next_path("/superset/dashboard/10/", fallback="/") == "/superset/dashboard/10/"


def test_safe_next_path_rejects_external() -> None:
    assert safe_next_path("//evil.example/phish", fallback="/home") == "/home"


def test_decode_portal_launch_token_valid(launch_app: Flask) -> None:
    token = _mint_token()
    with launch_app.app_context():
        claims = decode_portal_launch_token(token)
    assert claims is not None
    assert claims["sub"] == "t_demo-corp__cntt.cv@demo-corp"


def test_decode_portal_launch_token_rejects_bad_secret(launch_app: Flask) -> None:
    token = _mint_token(secret="wrong")
    with launch_app.app_context():
        assert decode_portal_launch_token(token) is None


def test_try_portal_launch_login_redirects(launch_app: Flask) -> None:
    token = _mint_token()
    mock_user = MagicMock()
    mock_user.is_active = True
    mock_sm = MagicMock()
    mock_sm.find_user.return_value = mock_user

    with launch_app.test_request_context(
        f"/login/?portal_launch={token}&next=/superset/dashboard/5/"
    ):
        with (
            patch("superset.security_manager", mock_sm),
            patch("superset.portal_launch.auth.login_user") as mock_login,
        ):
            response = try_portal_launch_login(
                launch_app.request,
                fallback_url="/superset/welcome/",
            )

    assert response is not None
    assert response.status_code == 302
    assert response.location == "/superset/dashboard/5/"
    mock_login.assert_called_once_with(mock_user, remember=False)
    mock_sm.on_user_login.assert_called_once_with(mock_user)
