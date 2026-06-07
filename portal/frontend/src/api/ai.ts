/**
 * Licensed to the Apache Software Foundation (ASF) under one
 * or more contributor license agreements.  See the NOTICE file
 * distributed with this work for additional information
 * regarding copyright ownership.  The ASF licenses this file
 * to you under the Apache License, Version 2.0 (the
 * "License"); you may not use this file except in compliance
 * with the License.  You may obtain a copy of the License at
 *
 *   http://www.apache.org/licenses/LICENSE-2.0
 *
 * Unless required by applicable law or agreed to in writing,
 * software distributed under the License is distributed on an
 * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
 * KIND, either express or implied.  See the License for the
 * specific language governing permissions and limitations
 * under the License.
 */
import { ApiError, apiFetch } from '@/api/auth';

export interface GenerateSqlPayload {
  prompt: string;
  context_sql?: string;
  dataset_hint?: string;
}

export interface GenerateSqlResult {
  sql: string;
}

export interface McpTokenResult {
  token: string;
  expires_in_seconds: number;
  superset_username: string;
}

export type SqlStreamEvent =
  | { type: 'chunk'; content: string }
  | { type: 'done' }
  | { type: 'error'; message: string };

const API_BASE = import.meta.env.VITE_API_URL ?? '';

export async function generateSql(
  payload: GenerateSqlPayload,
): Promise<GenerateSqlResult> {
  return apiFetch<GenerateSqlResult>('/ai/generate-sql', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function fetchMcpToken(): Promise<McpTokenResult> {
  return apiFetch<McpTokenResult>('/ai/mcp-token');
}

export async function streamGenerateSql(
  payload: GenerateSqlPayload,
  onEvent: (event: SqlStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  const response = await fetch(`${API_BASE}/ai/generate-sql/stream`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    throw new ApiError(await parseStreamError(response), response.status);
  }

  const reader = response.body?.getReader();
  if (!reader) {
    throw new ApiError('Streaming not supported', 500);
  }

  const decoder = new TextDecoder();
  let buffer = '';

  let streamDone = false;
  while (!streamDone) {
    const { done, value } = await reader.read();
    streamDone = done;
    if (value) {
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() ?? '';
      for (const part of parts) {
        const line = part
          .split('\n')
          .find((entry) => entry.startsWith('data:'));
        if (!line) {
          continue;
        }
        const json = line.slice(5).trim();
        if (!json) {
          continue;
        }
        onEvent(JSON.parse(json) as SqlStreamEvent);
      }
    }
  }
}

async function parseStreamError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? response.statusText;
  } catch {
    return response.statusText;
  }
}
