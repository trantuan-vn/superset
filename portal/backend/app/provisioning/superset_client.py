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
"""HTTP client for Superset REST API (service account)."""

from __future__ import annotations

import secrets
import string
from dataclasses import dataclass
from typing import Any

import httpx

from app.config import Settings, get_settings
from app.provisioning.rison import encode_rison


_PAGE_SIZE = 500


class SupersetClientError(Exception):
    """Raised when Superset API returns an error or is unreachable."""

    def __init__(self, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass(frozen=True)
class SupersetRole:
    id: int
    name: str
    permission_ids: tuple[int, ...]
    user_ids: tuple[int, ...]


@dataclass(frozen=True)
class SupersetUser:
    id: int
    username: str
    email: str
    active: bool
    role_ids: tuple[int, ...]


class SupersetClient:
    """Thin wrapper around Superset security REST endpoints."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._base_url = self._settings.superset_internal_url.rstrip("/")
        self._api_key = self._settings.superset_service_api_key

    @property
    def enabled(self) -> bool:
        return bool(self._api_key and self._base_url)

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(timeout=self._settings.provisioning_http_timeout) as client:
                response = client.request(
                    method,
                    url,
                    headers=self._headers(),
                    json=json_payload,
                    params=params,
                )
        except httpx.HTTPError as exc:
            raise SupersetClientError(f"Superset unreachable: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text[:500]
            raise SupersetClientError(
                f"Superset API {method} {path} failed ({response.status_code}): {detail}",
                status_code=response.status_code,
            )

        if not response.content:
            return {}
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"result": data}

    def _request_with_csrf(
        self,
        method: str,
        path: str,
        *,
        json_payload: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Mutating requests that require CSRF (e.g. Row Level Security API)."""
        url = f"{self._base_url}{path}"
        try:
            with httpx.Client(
                timeout=self._settings.provisioning_http_timeout,
                follow_redirects=True,
            ) as client:
                csrf_response = client.get(
                    f"{self._base_url}/api/v1/security/csrf_token/",
                    headers=self._headers(),
                )
                if csrf_response.status_code >= 400:
                    detail = csrf_response.text[:500]
                    raise SupersetClientError(
                        f"Superset CSRF token fetch failed ({csrf_response.status_code}): {detail}",
                        status_code=csrf_response.status_code,
                    )
                csrf_data = csrf_response.json()
                csrf_token = csrf_data.get("result")
                if not csrf_token:
                    raise SupersetClientError("Superset CSRF token missing in response")

                headers = {
                    **self._headers(),
                    "X-CSRF-Token": str(csrf_token),
                }
                response = client.request(
                    method,
                    url,
                    headers=headers,
                    json=json_payload,
                    params=params,
                )
        except SupersetClientError:
            raise
        except httpx.HTTPError as exc:
            raise SupersetClientError(f"Superset unreachable: {exc}") from exc

        if response.status_code >= 400:
            detail = response.text[:500]
            raise SupersetClientError(
                f"Superset API {method} {path} failed ({response.status_code}): {detail}",
                status_code=response.status_code,
            )

        if not response.content:
            return {}
        data = response.json()
        if isinstance(data, dict):
            return data
        return {"result": data}

    def health_check(self) -> bool:
        """Return True when Superset health endpoint responds."""
        try:
            with httpx.Client(timeout=5.0) as client:
                response = client.get(f"{self._base_url}/health")
            return response.status_code == 200
        except httpx.HTTPError:
            return False

    def find_role_by_name(self, role_name: str) -> SupersetRole | None:
        query = encode_rison(
            {
                "filters": [{"col": "name", "opr": "eq", "value": role_name}],
                "page": 0,
                "page_size": 1,
            }
        )
        data = self._request("GET", "/api/v1/security/roles/search/", params={"q": query})
        results = data.get("result") or []
        for role in results:
            if str(role.get("name")) != role_name:
                continue
            return SupersetRole(
                id=int(role["id"]),
                name=str(role["name"]),
                permission_ids=tuple(int(pid) for pid in role.get("permission_ids") or []),
                user_ids=tuple(int(uid) for uid in role.get("user_ids") or []),
            )
        return None

    def create_role(self, role_name: str) -> SupersetRole:
        data = self._request(
            "POST",
            "/api/v1/security/roles/",
            json_payload={"name": role_name},
        )
        role_id = int(data.get("id") or data.get("result", {}).get("id"))
        return SupersetRole(
            id=role_id,
            name=role_name,
            permission_ids=(),
            user_ids=(),
        )

    def update_role_name(self, role_id: int, role_name: str) -> None:
        self._request(
            "PUT",
            f"/api/v1/security/roles/{role_id}",
            json_payload={"name": role_name},
        )

    def set_role_permissions(self, role_id: int, permission_ids: list[int]) -> None:
        self._request(
            "POST",
            f"/api/v1/security/roles/{role_id}/permissions",
            json_payload={"permission_view_menu_ids": permission_ids},
        )

    def set_role_users(self, role_id: int, user_ids: list[int]) -> None:
        self._request(
            "PUT",
            f"/api/v1/security/roles/{role_id}/users",
            json_payload={"user_ids": user_ids},
        )

    def list_permissions_page(self, page: int, page_size: int) -> tuple[list[dict[str, Any]], int]:
        query = encode_rison({"page": page, "page_size": page_size})
        data = self._request(
            "GET",
            "/api/v1/security/permissions-resources/",
            params={"q": query},
        )
        results = data.get("result") or []
        total = int(data.get("count") or len(results))
        return results, total

    def find_user_by_username(self, username: str) -> SupersetUser | None:
        query = encode_rison(
            {
                "filters": [{"col": "username", "opr": "eq", "value": username}],
                "page": 0,
                "page_size": 1,
            }
        )
        data = self._request("GET", "/api/v1/security/users/", params={"q": query})
        results = data.get("result") or []
        for user in results:
            if str(user.get("username")) != username:
                continue
            role_ids = tuple(int(r["id"]) for r in user.get("roles") or [])
            return SupersetUser(
                id=int(user["id"]),
                username=str(user["username"]),
                email=str(user.get("email") or ""),
                active=bool(user.get("active", True)),
                role_ids=role_ids,
            )
        return None

    def create_user(
        self,
        *,
        username: str,
        email: str,
        first_name: str,
        last_name: str,
        role_ids: list[int],
        active: bool = True,
    ) -> SupersetUser:
        password = _random_password()
        payload = {
            "username": username,
            "email": email,
            "first_name": first_name,
            "last_name": last_name,
            "password": password,
            "active": active,
            "roles": role_ids,
        }
        data = self._request("POST", "/api/v1/security/users/", json_payload=payload)
        user_id = int(data.get("id") or data.get("result", {}).get("id"))
        return SupersetUser(
            id=user_id,
            username=username,
            email=email,
            active=active,
            role_ids=tuple(role_ids),
        )

    def update_user(
        self,
        user_id: int,
        *,
        email: str,
        first_name: str,
        last_name: str,
        role_ids: list[int],
        active: bool,
    ) -> None:
        self._request(
            "PUT",
            f"/api/v1/security/users/{user_id}",
            json_payload={
                "email": email,
                "first_name": first_name,
                "last_name": last_name,
                "roles": role_ids,
                "active": active,
            },
        )

    def find_dataset_ids_by_names(self, dataset_names: list[str]) -> list[int]:
        """Resolve Superset dataset IDs by table_name (best-effort)."""
        if not dataset_names:
            return []

        found: list[int] = []
        page = 0
        remaining = {name.strip() for name in dataset_names if name.strip()}

        while remaining:
            query = encode_rison({"page": page, "page_size": _PAGE_SIZE})
            data = self._request("GET", "/api/v1/dataset/", params={"q": query})
            results = data.get("result") or []
            if not results:
                break

            for item in results:
                table_name = str(item.get("table_name") or "")
                if table_name in remaining:
                    found.append(int(item["id"]))
                    remaining.discard(table_name)

            total = int(data.get("count") or 0)
            page += 1
            if not results or page * len(results) >= total:
                break

        return found

    def find_rls_rule_by_name(self, rule_name: str) -> int | None:
        query = encode_rison(
            {
                "filters": [{"col": "name", "opr": "eq", "value": rule_name}],
                "page": 0,
                "page_size": 1,
            }
        )
        data = self._request(
            "GET",
            "/api/v1/rowlevelsecurity/",
            params={"q": query},
        )
        results = data.get("result") or []
        for item in results:
            if str(item.get("name")) == rule_name:
                return int(item["id"])
        return None

    def create_rls_rule(
        self,
        *,
        name: str,
        clause: str,
        filter_type: str,
        table_ids: list[int],
        role_ids: list[int],
        description: str | None = None,
    ) -> int:
        payload: dict[str, Any] = {
            "name": name,
            "clause": clause,
            "filter_type": filter_type,
            "tables": table_ids,
            "roles": role_ids,
        }
        if description:
            payload["description"] = description
        data = self._request_with_csrf("POST", "/api/v1/rowlevelsecurity/", json_payload=payload)
        rule_id = data.get("id")
        if rule_id is None:
            raise SupersetClientError(f"Unexpected RLS create response: {data}")
        return int(rule_id)

    def update_rls_rule(
        self,
        rule_id: int,
        *,
        clause: str,
        filter_type: str,
        table_ids: list[int],
        role_ids: list[int],
        description: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "clause": clause,
            "filter_type": filter_type,
            "tables": table_ids,
            "roles": role_ids,
        }
        if description is not None:
            payload["description"] = description
        self._request_with_csrf(
            "PUT",
            f"/api/v1/rowlevelsecurity/{rule_id}",
            json_payload=payload,
        )

    def delete_rls_rule(self, rule_id: int) -> None:
        query = encode_rison([rule_id])
        self._request_with_csrf(
            "DELETE",
            "/api/v1/rowlevelsecurity/",
            params={"q": query},
        )


def _random_password(length: int = 32) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def split_display_name(display_name: str) -> tuple[str, str]:
    parts = display_name.strip().split(maxsplit=1)
    if not parts:
        return ("Portal", "User")
    if len(parts) == 1:
        return (parts[0], "-")
    return (parts[0], parts[1])
