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
"""OpenAI-compatible chat completions adapter."""

import json
import re
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.ai.adapters.base import LlmAdapter, SqlGenerationRequest

_SYSTEM_PROMPT = """You are a SQL assistant for Apache Superset export templates.
Return exactly one read-only PostgreSQL SELECT (or WITH … SELECT) statement.
Never include DML/DDL, comments about security bypass, or multiple statements.
Use Jinja macros {{ current_user_tenant() }} and {{ current_user_dept() }} when
filtering by tenant or department. Respond with SQL only — no markdown fences."""


def _extract_sql(content: str) -> str:
    fenced = re.search(r"```(?:sql)?\s*([\s\S]*?)```", content, flags=re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()
    return content.strip()


class OpenAiCompatibleAdapter(LlmAdapter):
    """Calls an OpenAI-compatible /v1/chat/completions endpoint."""

    def __init__(
        self,
        *,
        endpoint: str,
        model: str,
        api_key: str | None,
        timeout: float = 60.0,
    ) -> None:
        self._endpoint = endpoint.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        return headers

    def _messages(self, request: SqlGenerationRequest) -> list[dict[str, str]]:
        user_parts = [f"Request: {request.prompt.strip()}"]
        if request.dataset_hint:
            user_parts.append(f"Preferred dataset/table: {request.dataset_hint}")
        if request.context_sql:
            user_parts.append(f"Existing SQL draft:\n{request.context_sql.strip()}")
        return [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": "\n\n".join(user_parts)},
        ]

    async def generate_sql(self, request: SqlGenerationRequest) -> str:
        payload = {
            "model": self._model,
            "messages": self._messages(request),
            "temperature": 0.1,
            "stream": False,
        }
        url = f"{self._endpoint}/v1/chat/completions"
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, headers=self._headers(), json=payload)
            response.raise_for_status()
            body: dict[str, Any] = response.json()
        choices = body.get("choices") or []
        if not choices:
            raise ValueError("LLM returned no choices")
        message = choices[0].get("message") or {}
        content = str(message.get("content") or "").strip()
        if not content:
            raise ValueError("LLM returned empty content")
        return _extract_sql(content)

    async def stream_sql(self, request: SqlGenerationRequest) -> AsyncIterator[str]:
        payload = {
            "model": self._model,
            "messages": self._messages(request),
            "temperature": 0.1,
            "stream": True,
        }
        url = f"{self._endpoint}/v1/chat/completions"
        buffer = ""
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                url,
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    chunk = json.loads(data)
                    delta = (
                        (chunk.get("choices") or [{}])[0]
                        .get("delta", {})
                        .get("content")
                    )
                    if delta:
                        buffer += str(delta)
                        yield str(delta)
        if not buffer.strip():
            raise ValueError("LLM stream returned empty content")
