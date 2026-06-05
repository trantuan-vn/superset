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

export interface TenantSettings {
  tenant_id: string;
  sso_ldap_enabled: boolean;
  auth_mode: 'local' | 'oidc' | 'saml' | 'ldap';
  ldap_migration_required?: boolean;
  sso_config: Record<string, unknown> | null;
  digital_signature_enabled: boolean;
  pki_config: Record<string, unknown> | null;
  ai_enabled: boolean;
  ai_config: Record<string, unknown> | null;
  export_formats: string[] | null;
  download_token_ttl_hours: number;
  branding: Record<string, unknown> | null;
}

export interface TenantSettingsPatch {
  sso_ldap_enabled?: boolean;
  auth_mode?: TenantSettings['auth_mode'];
  sso_config?: Record<string, unknown>;
  digital_signature_enabled?: boolean;
  branding?: Record<string, unknown>;
  /** Required when first enabling LDAP — must match Portal password(s) to migrate. */
  portal_password?: string;
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

export async function fetchTenantSettings(
  tenantId: string,
): Promise<TenantSettings> {
  return apiFetch<TenantSettings>(`/tenants/${tenantId}/settings`);
}

export async function updateTenantSettings(
  tenantId: string,
  patch: TenantSettingsPatch,
): Promise<TenantSettings> {
  return apiFetch<TenantSettings>(`/tenants/${tenantId}/settings`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
}
