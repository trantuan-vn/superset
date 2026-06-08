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
import type { ExportTemplate } from '@/api/templates';

export type TransactionStatus =
  | 'draft'
  | 'submitted'
  | 'approved'
  | 'rejected'
  | 'downloaded';

export interface ExportTransaction {
  id: string;
  tenant_id: string;
  template_id: string;
  template_name: string | null;
  department_id: string;
  params_json: Record<string, unknown>;
  status: TransactionStatus;
  reject_comment: string | null;
  request_reason: string | null;
  created_by: string;
  created_by_name: string | null;
  submitted_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  created_at: string;
  updated_at: string;
}

export async function fetchDeptTemplates(): Promise<ExportTemplate[]> {
  return apiFetch<ExportTemplate[]>('/dept/templates');
}

export async function fetchMyTransactions(): Promise<ExportTransaction[]> {
  return apiFetch<ExportTransaction[]>('/transactions');
}

export async function fetchPendingTransactions(): Promise<ExportTransaction[]> {
  return apiFetch<ExportTransaction[]>('/transactions/pending');
}

export async function createTransaction(
  templateId: string,
  reason: string,
): Promise<ExportTransaction> {
  return apiFetch<ExportTransaction>('/transactions', {
    method: 'POST',
    body: JSON.stringify({ template_id: templateId, reason, params_json: {} }),
  });
}

export async function submitTransaction(id: string): Promise<ExportTransaction> {
  return apiFetch<ExportTransaction>(`/transactions/${id}/submit`, { method: 'POST' });
}

export async function approveTransaction(id: string): Promise<ExportTransaction> {
  return apiFetch<ExportTransaction>(`/transactions/${id}/approve`, { method: 'POST' });
}

export async function rejectTransaction(
  id: string,
  comment: string,
): Promise<ExportTransaction> {
  return apiFetch<ExportTransaction>(`/transactions/${id}/reject`, {
    method: 'POST',
    body: JSON.stringify({ comment }),
  });
}

export async function downloadTransaction(
  id: string,
  format: 'csv' | 'pdf',
): Promise<void> {
  const API_BASE = import.meta.env.VITE_API_URL ?? '';
  const response = await fetch(
    `${API_BASE}/transactions/${id}/download?format=${format}`,
    {
      method: 'POST',
      credentials: 'include',
    },
  );
  if (!response.ok) {
    throw new ApiError(await response.text(), response.status);
  }
  const blob = await response.blob();
  const disposition = response.headers.get('Content-Disposition') ?? '';
  const match = disposition.match(/filename="([^"]+)"/);
  const filename = match?.[1] ?? `export.${format}`;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export { ApiError };
