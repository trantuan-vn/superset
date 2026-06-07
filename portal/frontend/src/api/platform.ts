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

import { ApiError } from '@/api/auth';

const API_BASE = import.meta.env.VITE_API_URL ?? '';

export interface PlatformTenant {
  id: string;
  slug: string;
  name: string;
  status: string;
  admin_count: number;
  pki_enabled: boolean;
}

export interface TenantAdmin {
  id: string;
  email: string;
  display_name: string;
}

export interface CreateTenantPayload {
  slug: string;
  name: string;
  admin_email: string;
  admin_password: string;
  admin_display_name: string;
}

export interface CreateTenantResult {
  tenant: PlatformTenant;
  admin: TenantAdmin;
}

export interface CreateTenantAdminPayload {
  admin_email: string;
  admin_password: string;
  admin_display_name: string;
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

export async function fetchPlatformTenants(): Promise<PlatformTenant[]> {
  return apiFetch<PlatformTenant[]>('/platform/tenants');
}

export async function createPlatformTenant(
  payload: CreateTenantPayload,
): Promise<CreateTenantResult> {
  return apiFetch<CreateTenantResult>('/platform/tenants', {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export async function addTenantAdmin(
  tenantId: string,
  payload: CreateTenantAdminPayload,
): Promise<TenantAdmin> {
  return apiFetch<TenantAdmin>(`/platform/tenants/${tenantId}/admins`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}
