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

const API_BASE = import.meta.env.VITE_API_URL ?? '';

export type TemplateStatus = 'draft' | 'review' | 'published' | 'archived';

export interface SharedDepartment {
  id: string;
  code: string;
  name: string;
}

export interface ExportTemplate {
  id: string;
  tenant_id: string;
  name: string;
  description: string | null;
  sql_snapshot: string;
  status: TemplateStatus;
  share_mode: 'ALL' | 'SELECTED' | null;
  share_scope_version: number;
  shared_departments?: SharedDepartment[];
  reject_comment: string | null;
  created_by: string;
  created_by_name: string | null;
  published_by: string | null;
  superset_dashboard_id: number | null;
  superset_dashboard_title: string | null;
  superset_dataset_id: number | null;
  submitted_at: string | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface TemplatePreviewResult {
  columns: string[];
  rows: Record<string, string>[];
  row_count: number;
  truncated: boolean;
  mock?: boolean;
}

export interface CreateTemplatePayload {
  name: string;
  description?: string;
  sql_snapshot: string;
}

export interface UpdateTemplatePayload {
  name?: string;
  description?: string;
  sql_snapshot?: string;
}

export interface TemplateApprovePayload {
  share_mode: 'ALL' | 'SELECTED';
  department_ids?: string[];
  certificate?: string;
  signature?: string;
}

export type SupersetLaunchTarget =
  | 'dataset'
  | 'dashboard_design'
  | 'dashboard_review'
  | 'dashboard_view';

export interface TemplateLaunchUrlResponse {
  url: string;
  target: SupersetLaunchTarget;
}

export interface PkiStepUpChallenge {
  nonce: string;
  expires_in_seconds: number;
  action: string;
}

class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

async function parseError(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: string };
    return body.detail ?? response.statusText;
  } catch {
    return response.statusText;
  }
}

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  if (!response.ok) {
    throw new ApiError(await parseError(response), response.status);
  }
  return response.json() as Promise<T>;
}

export async function fetchTemplates(params?: {
  status?: TemplateStatus;
  pending?: boolean;
}): Promise<ExportTemplate[]> {
  const search = new URLSearchParams();
  if (params?.status) {
    search.set('status', params.status);
  }
  if (params?.pending) {
    search.set('pending', 'true');
  }
  const query = search.toString();
  return apiFetch<ExportTemplate[]>(`/templates${query ? `?${query}` : ''}`);
}

export async function fetchTemplate(id: string): Promise<ExportTemplate> {
  return apiFetch<ExportTemplate>(`/templates/${id}`);
}

export async function createTemplate(
  payload: CreateTemplatePayload,
): Promise<ExportTemplate> {
  return apiFetch<ExportTemplate>('/templates', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function updateTemplate(
  id: string,
  payload: UpdateTemplatePayload,
): Promise<ExportTemplate> {
  return apiFetch<ExportTemplate>(`/templates/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(payload),
  });
}

export async function submitTemplate(id: string): Promise<ExportTemplate> {
  return apiFetch<ExportTemplate>(`/templates/${id}/submit`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export async function rejectTemplate(
  id: string,
  comment: string,
): Promise<ExportTemplate> {
  return apiFetch<ExportTemplate>(`/templates/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  });
}

export async function approveTemplate(
  id: string,
  payload: TemplateApprovePayload,
): Promise<ExportTemplate> {
  return apiFetch<ExportTemplate>(`/templates/${id}/approve`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function previewTemplate(
  id: string,
  sql?: string,
): Promise<TemplatePreviewResult> {
  return apiFetch<TemplatePreviewResult>(`/templates/${id}/preview`, {
    method: 'POST',
    body: JSON.stringify({ sql: sql ?? null }),
  });
}

export async function pushTemplateDataset(id: string): Promise<ExportTemplate> {
  return apiFetch<ExportTemplate>(`/templates/${id}/push-dataset`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export async function syncTemplateDashboard(id: string): Promise<ExportTemplate> {
  return apiFetch<ExportTemplate>(`/templates/${id}/sync-dashboard`, {
    method: 'POST',
    body: JSON.stringify({}),
  });
}

export async function fetchTemplateLaunchUrl(
  id: string,
  target: SupersetLaunchTarget,
): Promise<TemplateLaunchUrlResponse> {
  const params = new URLSearchParams({ target });
  return apiFetch<TemplateLaunchUrlResponse>(
    `/templates/${id}/launch-url?${params.toString()}`,
  );
}

export async function fetchTemplateStepUpChallenge(
  action = 'template_approve',
): Promise<PkiStepUpChallenge> {
  const params = new URLSearchParams({ action });
  return apiFetch<PkiStepUpChallenge>(
    `/templates/pki/step-up/challenge?${params.toString()}`,
    { method: 'POST', body: JSON.stringify({}) },
  );
}

export { ApiError };
