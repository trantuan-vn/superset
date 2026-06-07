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
"""LLM adapter interface."""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class SqlGenerationRequest:
    """Input for SQL generation."""

    prompt: str
    context_sql: str | None = None
    dataset_hint: str | None = None


class LlmAdapter(ABC):
    """Provider-agnostic SQL generation adapter."""

    @abstractmethod
    async def generate_sql(self, request: SqlGenerationRequest) -> str:
        """Return a complete SQL draft."""

    async def stream_sql(self, request: SqlGenerationRequest) -> AsyncIterator[str]:
        """Stream SQL chunks; default falls back to single-shot generation."""
        sql = await self.generate_sql(request)
        yield sql
