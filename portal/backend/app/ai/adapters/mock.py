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
"""Deterministic mock LLM for local development."""

from collections.abc import AsyncIterator

from app.ai.adapters.base import LlmAdapter, SqlGenerationRequest


class MockLlmAdapter(LlmAdapter):
    """Returns a safe SELECT template based on the user prompt."""

    async def generate_sql(self, request: SqlGenerationRequest) -> str:
        table = request.dataset_hint or "portal_export_data"
        prompt = request.prompt.strip().replace("'", "''")
        if request.context_sql and request.context_sql.strip():
            return (
                f"-- Refined from existing draft\n"
                f"SELECT *\n"
                f"FROM {table}\n"
                f"WHERE tenant_id = '{{{{ current_user_tenant() }}}}'\n"
                f"  -- intent: {prompt[:120]}\n"
                f"LIMIT 100"
            )
        return (
            f"-- Generated from prompt: {prompt[:120]}\n"
            f"SELECT *\n"
            f"FROM {table}\n"
            f"WHERE tenant_id = '{{{{ current_user_tenant() }}}}'\n"
            f"LIMIT 100"
        )

    async def stream_sql(self, request: SqlGenerationRequest) -> AsyncIterator[str]:
        sql = await self.generate_sql(request)
        chunk_size = 24
        for index in range(0, len(sql), chunk_size):
            yield sql[index : index + chunk_size]
