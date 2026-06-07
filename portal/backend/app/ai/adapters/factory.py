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
"""Resolve tenant ai_config to a concrete LLM adapter."""

from typing import Any

from app.ai.adapters.base import LlmAdapter
from app.ai.adapters.mock import MockLlmAdapter
from app.ai.adapters.openai_compatible import OpenAiCompatibleAdapter
from app.auth.secrets import resolve_secret_ref


def _resolve_api_key(ai_config: dict[str, Any]) -> str | None:
    ref = ai_config.get("api_key_ref")
    if ref:
        resolved = resolve_secret_ref(str(ref))
        if resolved:
            return resolved
    plain = ai_config.get("api_key")
    return str(plain) if plain else None


def get_llm_adapter(ai_config: dict[str, Any] | None) -> LlmAdapter:
    """Pick adapter from tenant ai_config; mock when provider unset."""
    config = ai_config or {}
    provider = str(config.get("provider") or "mock").lower()
    if provider in ("mock", "dev", ""):
        return MockLlmAdapter()

    endpoint = str(config.get("endpoint") or "").strip()
    model = str(config.get("model") or "gpt-4o-mini").strip()
    if not endpoint:
        return MockLlmAdapter()

    return OpenAiCompatibleAdapter(
        endpoint=endpoint,
        model=model,
        api_key=_resolve_api_key(config),
        timeout=float(config.get("timeout_seconds") or 60),
    )
